def test_dashboard_summary_and_history(client):
    client.delete('/invoices/session')
    created = client.post('/invoices/process', data={'sample_key':'happy'}); assert created.status_code == 200, created.text[:300]
    summary = client.get('/invoices/summary'); assert summary.status_code == 200, summary.text[:300]
    s = summary.json(); assert s['total'] >= 1 and s['approve'] >= 1
    history = client.get('/invoices/history'); assert history.status_code == 200, history.text[:300]
    assert any(x['id'] == created.json()['id'] for x in history.json())
