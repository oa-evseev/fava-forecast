import pytest
import fava_forecast.errors as err


@pytest.mark.parametrize("exc", [err.BeanQueryError, err.PriceParseError])
def test_custom_exceptions_inherit_and_message(exc):
    e = exc("test message")
    assert isinstance(e, RuntimeError)
    assert "test message" in str(e)
