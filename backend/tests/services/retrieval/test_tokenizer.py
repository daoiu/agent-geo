"""① 混合检索管道:领域分词 tokenizer 测试。

覆盖三件事:缺文件不抛、用户词典保护专有名词、切词丢弃长度 ≤1 token。
"""
from app.services.retrieval.tokenizer import load_domain_dict, tokenize


def test_load_missing_dict_returns_false(tmp_path):
    assert load_domain_dict(tmp_path / "nope.txt") is False


def test_domain_word_not_split(tmp_path):
    d = tmp_path / "geo_terms.txt"
    d.write_text("LangChain 100 n\nGPT-4o 100 n\n", encoding="utf-8")
    assert load_domain_dict(d) is True
    toks = tokenize("我在用 LangChain 和 GPT-4o 做检索")
    assert "LangChain" in toks
    assert "GPT-4o" in toks


def test_tokenize_drops_short_and_blank():
    toks = tokenize("a 检索 的")
    assert "检索" in toks
    assert "a" not in toks  # 长度 ≤1 丢弃