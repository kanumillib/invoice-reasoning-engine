def test_seeded_purchase_orders_visible(client):
    r = client.get('/invoices/pos')
    assert r.status_code == 200, r.text[:300]
    rows = r.json(); assert len(rows) == 6
    assert {x['po_number'] for x in rows} == {'PO-1001','PO-1002','PO-1003','PO-1004','PO-1005','PO-1006'}
