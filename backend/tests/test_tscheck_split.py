def test_split_po_progression(client):
    client.delete('/invoices/session')
    r1 = client.post('/invoices/process', data={'sample_key':'split-1'}); assert r1.status_code == 200, r1.text[:300]
    b1 = r1.json(); assert b1['decision'] == 'pending'; assert b1['reason_code'] == 'partial'; assert b1['progress_pct'] < 100
    r2 = client.post('/invoices/process', data={'sample_key':'split-2'}); assert r2.status_code == 200, r2.text[:300]
    b2 = r2.json(); assert b2['decision'] == 'approve'; assert b2['reason_code'] == 'within_tolerance'; assert b2['cumulative_amount'] >= b1['cumulative_amount']
