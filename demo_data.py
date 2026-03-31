"""Demo/mock data — used when DEMO_MODE=true (no API keys required).

Bug fix vs. prototype: removed unused `import random`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from models import Event, Source, Urgency

_NOW = datetime.now(timezone.utc)


def _ago(minutes: int) -> datetime:
    return _NOW - timedelta(minutes=minutes)


# ── Mock Events ───────────────────────────────────────────────

MOCK_SLACK_EVENTS = [
    Event(
        source=Source.SLACK,
        title="Client message in #client-pharma",
        body="Hey team, the invoice PDF parser is giving wrong totals for March invoices. Can someone look at this today? Our CA team is waiting.",
        url="https://livoai.slack.com/archives/C05PHARMA/p1711400000",
        timestamp=_ago(45),
        metadata={"user": "Ritu (PharmaCorp)", "channel": "client-pharma"},
    ),
    Event(
        source=Source.SLACK,
        title="Team discussion in #engineering",
        body="Pushed the new chunking strategy for the doc pipeline. Embeddings are 15% more accurate on the insurance test set now.",
        url="https://livoai.slack.com/archives/C05ENG/p1711401000",
        timestamp=_ago(20),
        metadata={"user": "Arjun", "channel": "engineering"},
    ),
    Event(
        source=Source.SLACK,
        title="Client message in #client-insurance",
        body="The search results on the portal are much better this week. Good work! One thing though — can we add a date filter?",
        url="https://livoai.slack.com/archives/C05INS/p1711402000",
        timestamp=_ago(10),
        metadata={"user": "Meena (InsureCo)", "channel": "client-insurance"},
    ),
    Event(
        source=Source.SLACK,
        title="Message in #general",
        body="Reminder: Friday standup moved to 3pm this week. Also, we're ordering lunch for the offsite planning session.",
        url="https://livoai.slack.com/archives/C05GEN/p1711403000",
        timestamp=_ago(5),
        metadata={"user": "Priya", "channel": "general"},
    ),
]

MOCK_GITHUB_EVENTS = [
    Event(
        source=Source.GITHUB,
        title="PR merged: Fix PDF table extraction for multi-page invoices",
        body="Resolved edge case where tables spanning multiple pages were split incorrectly. Added 12 test cases covering CA firm invoice formats.",
        url="https://github.com/livo-ai/doc-pipeline/pull/247",
        timestamp=_ago(35),
        metadata={"repo": "livo-ai/doc-pipeline", "state": "merged", "user": "arjun-dev"},
    ),
    Event(
        source=Source.GITHUB,
        title="CI Failed: pharma-portal main branch",
        body="Test suite failed on main branch after dependency update. 3 tests failing in the search module. Error: FAISS index dimension mismatch after model update.",
        url="https://github.com/livo-ai/pharma-portal/actions/runs/12345",
        timestamp=_ago(15),
        metadata={"repo": "livo-ai/pharma-portal", "workflow": "CI/CD Pipeline"},
    ),
    Event(
        source=Source.GITHUB,
        title="PR opened: Add date filter to insurance search portal",
        body="Implements the date range filter requested by InsureCo. Uses Elasticsearch date_range query. Ready for review.",
        url="https://github.com/livo-ai/insurance-portal/pull/89",
        timestamp=_ago(25),
        metadata={"repo": "livo-ai/insurance-portal", "state": "open", "user": "neha-dev"},
    ),
]

MOCK_NOTION_EVENTS = [
    Event(
        source=Source.NOTION,
        title="Task BLOCKED: Pharma Portal - SSO Integration",
        body="Waiting on PharmaCorp IT team to provide SAML metadata. Sent follow-up email 2 days ago, no response. This blocks the March 28 demo.",
        url="https://notion.so/livo/task-sso-integration",
        timestamp=_ago(60),
        metadata={"status": "blocked", "assignee": "Arjun", "due_date": "2026-03-28"},
    ),
    Event(
        source=Source.NOTION,
        title="Task completed: Insurance Portal - Search Relevance v2",
        body="Deployed new embedding model and reindexed all documents. Client confirmed the results are much better now.",
        url="https://notion.so/livo/task-search-v2",
        timestamp=_ago(40),
        metadata={"status": "done", "assignee": "Neha", "due_date": "2026-03-25"},
    ),
    Event(
        source=Source.NOTION,
        title="Task in-progress: Nonprofit Dashboard - Donor Report Generator",
        body="Building the PDF report template. 60% complete, on track for Friday delivery.",
        url="https://notion.so/livo/task-donor-reports",
        timestamp=_ago(30),
        metadata={"status": "in_progress", "assignee": "Vikram", "due_date": "2026-03-28"},
    ),
    Event(
        source=Source.NOTION,
        title="Task OVERDUE: CA Firm - Monthly Reconciliation Automation",
        body="Was due March 24. Delayed because the bank statement format changed. Need 2 more days.",
        url="https://notion.so/livo/task-reconciliation",
        timestamp=_ago(120),
        metadata={"status": "in_progress", "assignee": "Arjun", "due_date": "2026-03-24"},
    ),
]


def get_all_mock_events() -> List[Event]:
    all_events = MOCK_SLACK_EVENTS + MOCK_GITHUB_EVENTS + MOCK_NOTION_EVENTS
    return sorted(all_events, key=lambda e: e.timestamp, reverse=True)


# ── Mock LLM responses ────────────────────────────────────────

MOCK_DIGEST_SUMMARY = """URGENT:
- PharmaCorp client reported invoice PDF parser errors — CA team is waiting. Needs same-day fix.
- CI pipeline broken on pharma-portal main branch (FAISS dimension mismatch after model update).
- SSO integration for Pharma Portal is BLOCKED — waiting on client IT team since 2 days. This blocks the March 28 demo.
- CA firm reconciliation task is OVERDUE (was due March 24). Arjun needs 2 more days.

INFORMATIONAL:
- InsureCo is happy with search improvements, requested a date filter (PR already open).
- Doc pipeline PR merged — PDF table extraction fix with 12 new tests.
- Nonprofit donor report generator is 60% done, on track for Friday.
- Friday standup moved to 3pm.

SUMMARY: Four items need your attention today — a client-reported bug, a broken CI pipeline, a blocked task threatening the March 28 demo, and an overdue deliverable. Everything else is on track."""


MOCK_RAG_ANSWER = """Based on the project data, the pharma portal has a CI pipeline failure on the main branch caused by a FAISS index dimension mismatch after a model update. Additionally, the SSO integration task is blocked waiting on PharmaCorp's IT team to provide SAML metadata, which threatens the March 28 demo. The invoice PDF parser bug reported by the client is being prioritized for a same-day fix."""


# ── Mock YouTube transcript chunks ────────────────────────────

MOCK_VIDEO_CHUNKS: Dict[str, Dict] = {
    "aircAruvnKk": {
        "title": "But what is a Neural Network?",
        "url": "https://youtube.com/watch?v=aircAruvnKk",
        "chunks": [
            {"timestamp": "00:00", "text": "The brain is made up of neurons, and what we want to do is build a computational analog. A neural network in the machine learning sense is really just a function, it takes in some input, say an image, and spits out some output, like a label. The network is organized into layers."},
            {"timestamp": "01:30", "text": "Between the input and output layers, there are hidden layers. Each neuron in a hidden layer holds a number, called its activation, between 0 and 1. The activation of a neuron in the second layer is determined by a weighted sum of all the activations in the first layer."},
            {"timestamp": "04:12", "text": "Why layers? The hope is that the first layer picks up on edges, the second on patterns and textures, the third on larger structures. This hierarchical feature detection is the core idea."},
            {"timestamp": "07:45", "text": "The weights and biases are the parameters of the network. Learning means finding the right set of weights and biases so the network correctly classifies digits. We use a cost function and gradient descent to minimize that cost."},
            {"timestamp": "11:20", "text": "ReLU, the rectified linear unit, has largely replaced the sigmoid in modern networks. Instead of squishing everything between 0 and 1, ReLU just outputs max(0, x). The gradient doesn't vanish for large values the way sigmoid's does."},
        ],
    },
    "wjZofJX0v4M": {
        "title": "Transformers, the tech behind LLMs",
        "url": "https://youtube.com/watch?v=wjZofJX0v4M",
        "chunks": [
            {"timestamp": "00:00", "text": "A transformer is the neural network architecture behind all large language models. Introduced in the 2017 paper Attention Is All You Need. The key insight is the attention mechanism, which lets the model look at all parts of the input simultaneously."},
            {"timestamp": "03:20", "text": "The attention mechanism works by computing three vectors for each token: a Query, a Key, and a Value. The query asks what am I looking for, the key says what do I contain, and the value is the actual information passed along."},
            {"timestamp": "07:00", "text": "Multi-head attention runs several attention operations in parallel. Each head can focus on a different type of relationship — one might track syntactic structure while another tracks semantic meaning."},
            {"timestamp": "10:45", "text": "Positional encoding is necessary because the transformer has no built-in notion of word order. Without positional encoding, the sentence 'dog bites man' would look identical to 'man bites dog' to the model."},
            {"timestamp": "14:30", "text": "The feed-forward network in each transformer block is where most of the parameters live — roughly two-thirds of the model's total parameters. It can be thought of as a lookup table that stores factual knowledge learned during training."},
        ],
    },
    "fHF22Wxuyw4": {
        "title": "What is Deep Learning?",
        "url": "https://youtube.com/watch?v=fHF22Wxuyw4",
        "chunks": [
            {"timestamp": "00:00", "text": "Deep learning is a subset of machine learning where we use neural networks with many layers. Traditional ML uses hand-crafted features. Deep learning automatically learns the features from raw data."},
            {"timestamp": "05:30", "text": "In traditional ML you might manually extract edges and corners from an image. In deep learning, the network learns these features itself through backpropagation. This is why deep learning excels at unstructured data like images, audio, and text."},
            {"timestamp": "10:00", "text": "Deep learning became practical because of three things: large datasets from the internet, GPU computing power, and algorithmic improvements like batch normalization, dropout, and better activation functions."},
            {"timestamp": "15:30", "text": "Convolutional neural networks use convolution that slides a small filter across the image. A 3x3 filter has only 9 parameters but can detect edges anywhere in the image. This parameter sharing is why CNNs work so well for images."},
        ],
    },
    "C6YtPJxNULA": {
        "title": "All About ML & Deep Learning",
        "url": "https://youtube.com/watch?v=C6YtPJxNULA",
        "chunks": [
            {"timestamp": "00:00", "text": "Machine learning is teaching computers to learn from data without being explicitly programmed. There are three main types: supervised learning, unsupervised learning, and reinforcement learning."},
            {"timestamp": "06:00", "text": "The bias-variance tradeoff is fundamental to ML. A model with high bias is too simple — it underfits. A model with high variance is too complex — it overfits. The sweet spot is finding a model that generalizes to new data."},
            {"timestamp": "12:00", "text": "Transfer learning: instead of training from scratch, take a model pre-trained on a large dataset and fine-tune it on your specific task. The early layers already know how to detect edges and textures."},
            {"timestamp": "24:00", "text": "The vanishing gradient problem occurs in very deep networks when gradients become extremely small. Sigmoid is particularly bad because its maximum gradient is only 0.25. After 10 layers, the gradient becomes negligibly small. ReLU and residual connections solve this."},
        ],
    },
}


def get_mock_video_chunks() -> List[Dict]:
    """Return mock video data in the same format as YouTubeTranscriptFetcher."""
    return [
        {
            "title": data["title"],
            "url": data["url"],
            "video_id": vid_id,
            "chunks": data["chunks"],
        }
        for vid_id, data in MOCK_VIDEO_CHUNKS.items()
    ]


# ── Mock QA pairs ─────────────────────────────────────────────

MOCK_QA_PAIRS = [
    {
        "question": "Why did ReLU replace sigmoid as the dominant activation function in modern neural networks?",
        "answer": "ReLU replaced sigmoid because it solves the vanishing gradient problem. Sigmoid's maximum gradient is 0.25, so after many layers the gradient becomes negligibly small. ReLU outputs max(0, x), so its gradient is either 0 or 1, allowing gradients to flow through deep networks without shrinking.",
        "source_video": "But what is a Neural Network?",
        "source_url": "https://youtube.com/watch?v=aircAruvnKk",
        "timestamp": "11:20",
        "section_description": "ReLU activation replacing sigmoid",
        "retrieval_challenge": "A chunk about the sigmoid function being used to squish weighted sums (01:30) is lexically similar but describes sigmoid's role, not why it was replaced.",
    },
    {
        "question": "In a transformer, what role does the feed-forward network play compared to the attention mechanism?",
        "answer": "The feed-forward network in each transformer block is where most parameters live — roughly two-thirds of the total. While the attention mechanism handles relationships between tokens, the feed-forward network processes each token independently and acts as a lookup table storing factual knowledge learned during training.",
        "source_video": "Transformers, the tech behind LLMs",
        "source_url": "https://youtube.com/watch?v=wjZofJX0v4M",
        "timestamp": "14:30",
        "section_description": "Feed-forward network role in transformers",
        "retrieval_challenge": "The multi-head attention chunk (07:00) discusses transformer components but focuses on attention heads, not the feed-forward network's knowledge storage role.",
    },
    {
        "question": "How does deep learning's approach to feature extraction differ from traditional machine learning?",
        "answer": "In traditional ML, engineers manually design and extract features like edges, corners, and textures from raw data before feeding them to a classifier. Deep learning eliminates this step — the network automatically learns hierarchical features from raw data through backpropagation.",
        "source_video": "What is Deep Learning?",
        "source_url": "https://youtube.com/watch?v=fHF22Wxuyw4",
        "timestamp": "05:30",
        "section_description": "Feature engineering: ML vs deep learning",
        "retrieval_challenge": "The chunk about three factors enabling deep learning (10:00) mentions related concepts but doesn't explain the feature extraction difference.",
    },
    {
        "question": "Why is positional encoding necessary in the transformer architecture?",
        "answer": "Transformers have no built-in notion of word order because attention operates on all tokens simultaneously. Without positional encoding, 'dog bites man' and 'man bites dog' would look identical to the model. The original paper used sine and cosine functions of different frequencies to inject position information.",
        "source_video": "Transformers, the tech behind LLMs",
        "source_url": "https://youtube.com/watch?v=wjZofJX0v4M",
        "timestamp": "10:45",
        "section_description": "Positional encoding for word order",
        "retrieval_challenge": "The Query-Key-Value attention chunk (03:20) discusses how tokens interact but doesn't address the ordering problem.",
    },
    {
        "question": "What is the vanishing gradient problem and which specific property of sigmoid makes it worse?",
        "answer": "The vanishing gradient problem occurs when gradients become extremely small as they backpropagate through many layers. Sigmoid is particularly bad because its maximum gradient is only 0.25. After 10 layers the gradient is multiplied by 0.25 ten times, becoming negligibly small. ReLU and residual connections solve this.",
        "source_video": "All About ML & Deep Learning",
        "source_url": "https://youtube.com/watch?v=C6YtPJxNULA",
        "timestamp": "24:00",
        "section_description": "Vanishing gradient and sigmoid's role",
        "retrieval_challenge": "The batch normalization chunk (18:00) also discusses training stability but addresses internal covariate shift, not vanishing gradients.",
    },
]
