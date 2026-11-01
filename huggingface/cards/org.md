# Health Transformation Lab

**Better health answers from AI, and better care for the millions of people who ask.** The lab builds open
benchmarks that check answers where medicine meets dentistry, and whether an answer helps someone get care.

| Benchmark | What it asks | Status |
|---|---|---|
| **PerioBench** | Can rules and AI find gum disease accurately in the dental record? | Built, on synthetic records |
| **OralHealthBench** | Do AI answers hold up in real-world cases where dentistry meets medicine, such as drug interactions? | Proposed |
| **AccessBench** | Does an answer help someone with no coverage, no car or no dentist nearby? | Proposed |

## Start here

1. **Open the quickstart in Colab:** [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/healthtransformationlab/health-transformation-lab-nlp/blob/main/notebooks/perio_bench_quickstart.ipynb)
   It loads the notes, trains a simple baseline in about a minute, and scores it beside the leaderboard.
2. **The data:** [perio-bench-notes](https://huggingface.co/datasets/healthtransformationlab/perio-bench-notes):
   3,484 training and 240 test notes, labelled with periodontal status.
3. **The results:** [perio-bench-results](https://huggingface.co/datasets/healthtransformationlab/perio-bench-results):
   what every method answered, and the leaderboard.

Also on [Kaggle](https://www.kaggle.com/jcblearning) · Code on
[github.com/healthtransformationlab](https://github.com/healthtransformationlab/health-transformation-lab-nlp) ·
Website [healthtransformationlab.org](https://healthtransformationlab.org)

**Personal learning project**, not affiliated with or endorsed by any employer, institution or vendor. All data
is synthetic: no real patients, not for clinical use.
