import asyncio
import uuid

from lib.db import client, db, ensure_indexes


SAMPLE_POS = [
    {"po_number": "PO-1001", "vendor_name": "Acme Corporation", "po_amount": 8500.0, "tolerance_pct": 5.0, "status": "open"},
    {"po_number": "PO-1002", "vendor_name": "Globex Industries", "po_amount": 10000.0, "tolerance_pct": 5.0, "status": "open"},
    {"po_number": "PO-1003", "vendor_name": "Northstar Industrial", "po_amount": 9500.0, "tolerance_pct": 5.0, "status": "open"},
    {"po_number": "PO-1004", "vendor_name": "Acme Corporation", "po_amount": 12000.0, "tolerance_pct": 3.0, "status": "open"},
    {"po_number": "PO-1005", "vendor_name": "Vertex Supplies", "po_amount": 6200.0, "tolerance_pct": 4.0, "status": "open"},
    {"po_number": "PO-1006", "vendor_name": "Globex Industries", "po_amount": 4800.0, "tolerance_pct": 5.0, "status": "closed"},
]


async def ensure_seed_data() -> None:
    for po in SAMPLE_POS:
        await db.purchase_orders.update_one({"po_number": po["po_number"]}, {"$setOnInsert": {**po, "id": str(uuid.uuid4())}}, upsert=True)


async def main() -> None:
    await ensure_indexes()
    await ensure_seed_data()
    client.close()


if __name__ == "__main__":
    asyncio.run(main())