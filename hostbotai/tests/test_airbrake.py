import pytest
from hostbotai.logger import get_logger

log = get_logger()

def test_error_raised():
    with pytest.raises(ValueError):
        try:
            raise ValueError
        except Exception as e:
            log.error(e)
            raise e
