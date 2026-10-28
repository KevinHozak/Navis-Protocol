import pytest

from services.task_toggle import toggle, ToggleConflict
from services import task_time


@pytest.mark.parametrize('link', [
    '[[https://www.schoolpay.com/|SchoolPay]]',
    '[SchoolPay](https://www.schoolpay.com/)',
    '[[SchoolPay]]',
])
def test_linked_school_lunch_checkbox_preserves_source(tmp_path, link):
    path = tmp_path / 'Tasks.md'
    source = f'- [ ] 🍱 Finance: Add funds for school lunch ({link})  \r\n'
    path.write_bytes(source.encode('utf-8'))
    request = dict(expected_content=source, line_number=1, is_checked=True,
                   target_text='🍱 Finance: Add funds for school lunch (SchoolPay)')
    result = toggle(tmp_path, path, request)
    assert result['saved']
    assert task_time.strip(path.read_bytes().decode('utf-8')).encode('utf-8') == source.replace('[ ]', '[x]', 1).encode('utf-8')
    with pytest.raises(ToggleConflict):
        toggle(tmp_path, path, request)
