from app.arxiv import ArxivClient


SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <updated>2023-08-02T00:00:00Z</updated>
    <published>2017-06-12T17:57:34Z</published>
    <title>Attention Is All You Need</title>
    <summary>  The dominant sequence transduction models are based...  </summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <arxiv:primary_category term="cs.CL" />
    <category term="cs.CL" />
    <category term="cs.LG" />
    <link href="http://arxiv.org/abs/1706.03762v7" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/1706.03762v7" rel="related" title="pdf" type="application/pdf"/>
  </entry>
</feed>
"""


def test_parse_entry_extracts_metadata():
    client = ArxivClient(interval=0.0)
    papers = client._parse(SAMPLE_ATOM)

    assert len(papers) == 1
    paper = papers[0]
    assert paper["arxiv_id"] == "1706.03762"
    assert paper["title"] == "Attention Is All You Need"
    assert paper["abstract"].startswith("The dominant sequence")
    assert paper["authors"] == ["Ashish Vaswani", "Noam Shazeer"]
    assert paper["categories"] == ["cs.CL", "cs.LG"]
    assert paper["published"] == "2017-06-12T17:57:34Z"
    assert paper["pdf_url"] == "https://arxiv.org/pdf/1706.03762"


def test_build_params_includes_query_and_category():
    client = ArxivClient(interval=0.0)
    params = client._build_params("neural networks", 10, "cs.AI")
    assert params["search_query"] == "all:neural networks AND cat:cs.AI"
    assert params["max_results"] == 10

    params_no_cat = client._build_params("neural networks", 5, None)
    assert params_no_cat["search_query"] == "all:neural networks"
