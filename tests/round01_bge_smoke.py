"""Offline synthetic BGE dimension check; no corpus or remote model."""
import json
from pathlib import Path
from qa_core.config.settings import Settings
from qa_core.retrieval.models import LocalEmbeddings


def main():
    try:
        vectors=LocalEmbeddings(Settings.from_env()).embed_documents(['synthetic QA fixture'])
        result={'status':'PASS','count':len(vectors),'dimension':len(vectors[0])}
    except Exception as exc:
        result={'status':'BLOCKED','error_type':type(exc).__name__}
    Path('local/round01/bge.json').write_text(json.dumps(result),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
