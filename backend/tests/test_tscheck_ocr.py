def test_scanned_ocr_fallback(client):
    client.delete('/invoices/session')
    r = client.post('/invoices/process', data={'sample_key':'scanned'})
    assert r.status_code == 200, r.text[:300]
    b = r.json(); assert b['extraction_method'] == 'ocr'; assert b['decision'] in {'approve','flag','reject','pending'}; assert b['reason']
