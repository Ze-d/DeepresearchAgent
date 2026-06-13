from deepresearch.evidence.ranking import (
    _classify_domain,
    _classify_source_type,
    _estimate_freshness,
    rank_sources,
)


class TestClassifyDomain:
    def test_edu_domain(self):
        name, score = _classify_domain("https://cs.stanford.edu/papers/ai")
        assert name == "edu"
        assert score == 1.0

    def test_gov_domain(self):
        name, score = _classify_domain("https://www.nist.gov/publication")
        assert name == "gov"
        assert score == 1.0

    def test_known_tech_domain(self):
        name, score = _classify_domain("https://arxiv.org/abs/2401.xxx")
        assert name == "arxiv"
        assert score == 0.8

    def test_github_domain(self):
        name, score = _classify_domain("https://github.com/langchain-ai/langgraph")
        assert name == "github"
        assert score == 0.8

    def test_org_domain(self):
        name, score = _classify_domain("https://www.python.org/dev/peps/")
        assert name == "org"
        assert score == 0.6

    def test_com_domain(self):
        name, score = _classify_domain("https://medium.com/tech-blog/post")
        assert name == "com"
        assert score == 0.5

    def test_social_domain(self):
        name, score = _classify_domain("https://www.reddit.com/r/MachineLearning/")
        assert name == "social"
        assert score == 0.2

    def test_unknown_tld(self):
        name, score = _classify_domain("https://example.xyz/page")
        assert name == "other"
        assert score == 0.4


class TestClassifySourceType:
    def test_academic_paper(self):
        tp, score = _classify_source_type("This paper presents...", "Abstract\n\nWe propose...")
        assert tp == "academic"
        assert score == 1.0

    def test_official_docs(self):
        tp, score = _classify_source_type("Documentation for...", "API Reference\n\nParameters...")
        assert tp == "official_docs"
        assert score == 0.9

    def test_tech_blog(self):
        tp, score = _classify_source_type("A blog post about AI", "")
        assert tp == "tech_blog"
        assert score == 0.6

    def test_unknown_type(self):
        tp, score = _classify_source_type("", "")
        assert tp == "unknown"
        assert score == 0.4


class TestEstimateFreshness:
    def test_recent_date(self):
        import datetime
        this_year = str(datetime.date.today().year)
        score = _estimate_freshness(f"Published in {this_year}")
        assert score == 1.0

    def test_three_years_old(self):
        import datetime
        three_years_ago = datetime.date.today().year - 3
        score = _estimate_freshness(f"Published {three_years_ago}")
        assert score == 0.7

    def test_old_date(self):
        score = _estimate_freshness("Published in 2010")
        assert score == 0.4

    def test_no_date(self):
        score = _estimate_freshness("No date information here")
        assert score == 0.5


class TestRankSources:
    def test_rank_and_sort(self):
        sources = [
            {"id": "s1", "title": "Reddit post", "url": "https://reddit.com/r/ai",
             "snippet": "", "content": "short", "source_type": "unknown", "score": 0.0},
            {"id": "s2", "title": "Paper", "url": "https://arxiv.org/abs/2401.xxx",
             "snippet": "We propose a new method", "content": "Abstract\n\n" + "x" * 3000,
             "source_type": "unknown", "score": 0.0},
            {"id": "s3", "title": "Docs", "url": "https://python.org/docs",
             "snippet": "Official documentation", "content": "x" * 1000,
             "source_type": "unknown", "score": 0.0},
        ]
        result = rank_sources(sources)
        # arxiv paper > python.org docs > reddit
        assert result[0]["id"] == "s2"
        assert result[0]["score"] > result[1]["score"]
        assert result[1]["score"] > result[2]["score"]

    def test_rank_with_existing_score(self):
        sources = [
            {"id": "s1", "title": "T", "url": "https://edu.cn/s", "snippet": "paper",
             "content": "long" * 500, "source_type": "unknown", "score": 0.99},
        ]
        result = rank_sources(sources)
        assert result[0]["score"] != 0.99  # 被重新计算了

    def test_empty_list(self):
        assert rank_sources([]) == []
