from app.llm.news_risk import NewsRiskGate

class FakeClient:
    def generate_json(self, prompt):
        return {'verdict': 'OPEN_LONG', 'reason': 'bad'}


def test_llm_invalid_verdict_becomes_unavailable():
    result = NewsRiskGate(FakeClient()).evaluate_text('news', 'BTCUSDT')
    assert result['verdict'] == 'UNAVAILABLE'
