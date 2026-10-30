"""Forge proposals and atomic, explicitly approved manifestation shared by both adapters."""

from __future__ import annotations
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager

from services.ai_provider import ProviderError


def get_provider():
    from services import ai_provider

    return ai_provider.get_provider()


FIELDS = (
    "name",
    "role",
    "gender",
    "height",
    "home_realm",
    "voice_id",
    "personality",
    "atmosphere",
    "description",
)
SECTORS = {"companion": "Companions", "realm": "Realms", "beast": "Obstacles/Beasts"}


class ForgeError(ValueError):
    pass


def validate(entity_type, name, blueprint=None):
    if not isinstance(entity_type, str) or entity_type.lower() not in SECTORS:
        raise ForgeError("Unsupported Forge entity type.")
    if (
        not isinstance(name, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _'-]{0,79}", name)
        or name != name.strip()
    ):
        raise ForgeError(
            "Use a name of 1-80 letters, numbers, spaces, apostrophes, underscores or hyphens."
        )
    if name.split(".")[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        raise ForgeError("Reserved entity name.")
    if entity_type.lower() == "companion" and name.lower() == "keeper":
        raise ForgeError("Keeper is a fixed party member and cannot be forged.")
    if blueprint is not None:
        if (
            not isinstance(blueprint, dict)
            or set(blueprint) != set(FIELDS)
            or blueprint["name"] != name
        ):
            raise ForgeError("Blueprint fields or name do not match the proposal.")
        for value in blueprint.values():
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 8000
                or any(ord(c) < 32 and c not in "\n\t" for c in value)
            ):
                raise ForgeError("Blueprint contains an invalid field.")
            if any(
                token in value.lower()
                for token in ("<", ">", "javascript:", "file://", "![[", "../", "..\\")
            ):
                raise ForgeError("Blueprint contains unsafe content.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,79}", blueprint["voice_id"]):
            raise ForgeError("Invalid voice identifier.")
    return entity_type.lower()


def destination(root, entity_type, name):
    kind = validate(entity_type, name)
    root = Path(root).resolve()
    target = root / SECTORS[kind] / name
    # Refuse redirected parents, including Windows junctions.
    for parent in [target, *target.parents]:
        if parent == root:
            break
        if parent.is_symlink() or (
            hasattr(parent, "is_junction") and parent.is_junction()
        ):
            raise ForgeError("Forge destination contains a redirected path.")
    if not target.resolve().is_relative_to(root):
        raise ForgeError("Forge destination escaped the Vault.")
    return target


def store(root):
    digest = hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:24]
    folder = Path(tempfile.gettempdir()) / "navis-forge" / digest
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def proposal_path(root, proposal_id):
    if not isinstance(proposal_id, str) or not re.fullmatch(
        r"[0-9a-f]{32}", proposal_id
    ):
        raise ForgeError("Invalid proposal identifier.")
    return store(root) / (proposal_id + ".json")


async def submit(root, request, provider=None, *, transient=False):
    kind = validate(request.get("entity_type"), request.get("name"))
    name, concept = request["name"], request.get("prompt")
    if not isinstance(concept, str) or not concept.strip() or len(concept) > 16000:
        raise ForgeError("Enter a concept of at most 16000 characters.")
    destination(root, kind, name)
    if destination(root, kind, name).exists():
        raise ForgeError("An entity already exists at this destination.")
    prompt = (
        "Create a blueprint for the following user concept. Return ONLY a JSON object "
        "with exactly these nonempty string fields: "
        + ", ".join(FIELDS)
        + ". voice_id must be an Edge TTS identifier. The name must match exactly.\n"
        + json.dumps({"entity_type": kind, "name": name, "concept": concept})
    )
    from services import forge_volatile
    try:
        proposal_id = forge_volatile.reserve(root) if transient else uuid.uuid4().hex
    except ValueError as exc:
        raise ForgeError(str(exc)) from None
    try:
        text = await (provider or get_provider()).generate(
            prompt, system="Return only the requested JSON object."
        )
        try:
            blueprint = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise ForgeError(
                "The local model returned invalid JSON. Retry generation."
            ) from exc
        validate(kind, name, blueprint)
        record = {
            "entity_type": kind,
            "name": name,
            "blueprint": blueprint,
            "created": time.time(),
        }
        if transient:
            forge_volatile.fill(root, proposal_id, record)
        else:
            proposal_path(root, proposal_id).write_text(json.dumps(record), encoding="utf-8")
    except BaseException:
        if transient:
            forge_volatile.discard(root, proposal_id)
        raise
    return {
        "status": "success",
        "blueprint": blueprint,
        "proposal_id": proposal_id,
        "target": str(destination(root, kind, name).relative_to(Path(root).resolve())),
    }


@contextmanager
def destination_lock(path):
    # OS locks release on crash. Retain the inode to avoid unlink races.
    with path.open("a+b") as handle:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ForgeError(
                    "This destination is already being manifested. Wait before retrying."
                ) from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ForgeError(
                    "This destination is already being manifested. Wait before retrying."
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def approve(root, request, progress=lambda message: None):
    if request.get("approved") is not True:
        raise ForgeError("Explicit approval is required before writing to the Vault.")
    proposal_id = request.get("proposal_id")
    transient = isinstance(proposal_id, str) and proposal_id.startswith("portal-")
    try:
        if transient:
            from services import forge_volatile
            record = forge_volatile.read(root, proposal_id)
        else:
            record = json.loads(proposal_path(root, proposal_id).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ForgeError(
            "Proposal is missing or discarded. Generate a new preview."
        ) from exc
    kind, name, blueprint = record["entity_type"], record["name"], record["blueprint"]
    validate(kind, name, blueprint)
    target = destination(root, kind, name)
    marker = target / ".forge-proposal"
    if marker.is_file() and marker.read_text() == proposal_id:
        return {"status": "success", "message": "Manifestation already complete."}
    if time.time() - record["created"] > 3600:
        raise ForgeError("Proposal expired. Generate a fresh preview.")
    lock = store(root) / (hashlib.sha256(str(target).encode()).hexdigest() + ".lock")
    with destination_lock(lock):
        if target.exists():
            raise ForgeError(
                "Destination already exists; Forge never overwrites entities."
            )
        # Staging is on the same volume for atomic directory publication.
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".forge-", dir=target.parent) as staged:
            staged_root = Path(staged)
            scripts = Path(__file__).resolve().parents[1] / "scripts" / "forge"
            args = [sys.executable, str(scripts / f"forge_{kind}.py"), name]
            mapping = {
                "realm": {"atmosphere": "atmosphere", "description": "description"},
                "companion": {
                    "role": "role",
                    "gender": "gender",
                    "height": "height",
                    "realm": "home_realm",
                    "voice": "voice_id",
                    "personality": "personality",
                    "description": "description",
                },
                "beast": {
                    "class": "role",
                    "height": "height",
                    "voice": "voice_id",
                    "personality": "personality",
                },
            }[kind]
            for flag, field in mapping.items():
                args.append("--" + flag + "=" + blueprint[field])
            env = {
                k: os.environ[k]
                for k in ("PATH", "SystemRoot", "TEMP", "TMP")
                if k in os.environ
            }
            env.update(
                NAVIS_ROOT=str(staged_root),
                PYTHONIOENCODING="utf-8",
                NAVIS_FORGE_STAGING="1",
            )
            progress("Creating validated entity with the controlled Forge script.")
            try:
                result = subprocess.run(
                    args, env=env, cwd=scripts, capture_output=True, timeout=60
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ForgeError(
                    "Controlled Forge script could not complete. No entity was published."
                ) from exc
            output = staged_root / SECTORS[kind] / name
            if result.returncode or not output.is_dir():
                raise ForgeError(
                    "Controlled Forge script failed. No entity was published."
                )
            profile = output / ("Realm.md" if kind == "realm" else "Profile.md")
            if not profile.is_file():
                raise ForgeError("Controlled Forge script returned incomplete output.")
            with profile.open("a", encoding="utf-8") as stream:
                stream.write(
                    "\n\n## Neural Blueprint\n" + json.dumps(blueprint, indent=2) + "\n"
                )
            (output / ".forge-proposal").write_text(proposal_id)
            destination(root, kind, name)
            progress("Publishing complete entity.")
            # On Windows rename refuses an existing target. No overwrite/retry append.
            if target.exists():
                raise ForgeError("Destination became occupied before publication.")
            output.rename(target)
        progress("Manifestation complete.")
        if transient:
            forge_volatile.discard(root, proposal_id)
        return {"status": "success", "message": "Manifestation complete."}


def discard(root, request):
    identity = request.get("proposal_id")
    if isinstance(identity, str) and identity.startswith("portal-"):
        from services import forge_volatile
        try:
            forge_volatile.discard(root, identity)
        except ValueError as exc:
            raise ForgeError(str(exc)) from None
    else:
        proposal_path(root, identity).unlink(missing_ok=True)
    return {"status": "success", "message": "Proposal discarded."}


def dispatch(root, action, request):
    if action == "submit":
        return asyncio.run(submit(root, request))
    if action == "approve":
        return approve(root, request)
    if action == "discard":
        return discard(root, request)
    raise ForgeError("Unsupported Forge action.")


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.read(65537))
        result = dispatch(os.environ["NAVIS_ROOT"], sys.argv[1], request)
        print(json.dumps({"http_status": 200, "body": result}))
    except (ForgeError, ProviderError) as exc:
        print(
            json.dumps(
                {
                    "http_status": 503 if isinstance(exc, ProviderError) else 400,
                    "body": {"detail": str(exc)},
                }
            )
        )
    except Exception:
        print(
            json.dumps(
                {
                    "http_status": 503,
                    "body": {
                        "detail": "Forge runtime unavailable. Verify Python dependencies and local model."
                    },
                }
            )
        )
