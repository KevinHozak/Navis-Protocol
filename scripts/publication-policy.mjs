// Path safeguards complement credential scanning; neither can assess prose or images.
export function isPrivatePath(name) {
  const base = name.split('/').at(-1);
  const example = /^\.env(?:\..*)?\.example$/.test(base);
  return /(^|\/)\.test-[^/]+\//.test(name)
    || /(^|\/)(?:\.publication|\.tools|\.worktrees|\.ssh|\.aws|\.azure|\.gcloud)\//.test(name)
    || /^(?:Journal|Bridge|Keeper|Library|Companions|Lounge|Navis-Vault|vault)\//.test(name)
    || /^(?:metadata\.jsonl|search_results\.json|sync_output\.txt)$/.test(base)
    || (!example && /^\.env(?:\.|$)|^\.envrc$/.test(base))
    || /(?:credentials.*|client_secret.*|service[-_]account.*|secrets.*|tokens?|token_.*|oauth.*)\.json$/i.test(base)
    || /\.(?:pem|key|p8|p12|pfx|pkcs12|jks|keystore|mobileprovision|db|sqlite3?)(?:-|$)/i.test(base)
    || /\.(?:log|stackdump|bundle|dump|bak|zip|7z|tar|gz|tgz)$|\.backup/i.test(base);
}
