import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DB_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("FLASK_SECRET_KEY", "test")

from billing_service import (
    SQLALCHEMY_AVAILABLE,
    _fallback_add_kakin,
    _fallback_add_touchaku,
    _fallback_reset,
    query_billing,
)
from timeutil import now_jtc_naive

if SQLALCHEMY_AVAILABLE:
    from database import Base, get_engine, init_engine, session_scope
    from models import KakinJouhou, TouchakuKanri

    init_engine(os.environ["DB_URL"])
    Base.metadata.create_all(bind=get_engine())


def test_query_billing_returns_result():
    juryo_nichiji = now_jtc_naive()
    if SQLALCHEMY_AVAILABLE:
        with session_scope() as session:
            session.add(
                KakinJouhou(
                    record_shikibetsu=1,
                    record_no=1,
                    jigyosha_id="ABCD".ljust(15),
                    kakin_getsu="202401",
                    bandoru_id="BANDID123456789",
                    riyosha_bango="USER0000000001",
                    shohin_bango="PROD00000001",
                    seikyuu_kingaku=Decimal("1000"),
                    goriyo_kaishi_date="20240101",
                    goriyo_shuryo_date="20240131",
                    seikyusho_hyoji_mongon="Test",
                    yobi_char="-",
                )
            )
            session.add(
                TouchakuKanri(
                    juryo_nichiji=juryo_nichiji,
                    jigyosha_id="ABCD".ljust(15),
                    kakin_getsu="202401",
                    file_name="test.csv",
                    file_sakusei_date="20240101000000",
                    file_size=100,
                    sutoreji_path="https://example.blob.core.windows.net/kakinfiles/test.csv",
                    appurodo_moto="test",
                    status=1,
                )
            )
    else:
        _fallback_reset()
        _fallback_add_kakin(
            {
                "jigyosha_id": "ABCD",
                "kakin_getsu": "202401",
                "seikyuu_kingaku": 1000,
            }
        )
        _fallback_add_touchaku(
            {
                "jigyosha_id": "ABCD",
                "kakin_getsu": "202401",
                "juryo_nichiji": juryo_nichiji,
                "status": 1,
                "error_message": None,
            }
        )

    results, total = query_billing("ABCD", "202401", "juryo_nichiji", "desc", 1, 50)

    assert total == 1
    assert results[0]["total_amount"] == 1000
    assert results[0]["latest_received"] == juryo_nichiji
