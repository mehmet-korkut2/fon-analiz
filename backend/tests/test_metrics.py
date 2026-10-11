import pandas as pd
import pytest

from app.services.metrics import max_drawdown, total_return


def test_total_return():
    assert total_return(pd.Series([100, 110, 120])) == pytest.approx(0.20)


def test_max_drawdown():
    assert max_drawdown(pd.Series([100, 120, 90, 130])) == pytest.approx(-0.25)
