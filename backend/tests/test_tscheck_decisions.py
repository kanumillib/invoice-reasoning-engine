def test_decision_order_branches(client):
    client.delete('/invoices/session')
    for key, decision, reason in [('missing-total','flag','missing_data'), ('over-tolerance','flag','amount_mismatch')]:
        r = client.post('/invoices/process', data={'sample_key': key})
        assert r.status_code == 200, r.text[:300]
        b = r.json(); assert b['decision'] == decision; assert b['reason_code'] == reason
        assert b['reason']
