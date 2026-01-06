"""Multi-Source Certificate Transparency Logs - Query multiple free CT log sources"""
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Set
import asyncio
from utils.logger import logger
from utils.helpers import clean_domain, is_valid_domain


class MultiCTLogsService:
    """Service for querying MULTIPLE Certificate Transparency log sources (all free)"""

    # High-value AI-related patterns for crt.sh queries
    # EXPANDED: 300+ patterns for maximum discovery coverage
    # These are queried individually to avoid timeout from %.ai wildcard
    CRT_SH_PATTERNS = [
        # Core AI terms
        "chat", "bot", "ai", "gpt", "llm", "agent", "auto",
        "code", "write", "build", "gen", "ask", "think",
        "api", "app", "dev", "hub", "lab", "pro", "io",
        "data", "learn", "model", "deep", "neural", "brain",
        "voice", "image", "video", "text", "audio", "vision",
        "flow", "sync", "spark", "nova", "meta", "core",

        # AI/ML specific
        "ml", "nlp", "cv", "transformer", "diffusion", "stable",
        "prompt", "copilot", "assist", "helper", "magic", "wizard",
        "predict", "classify", "detect", "recognize", "generate",
        "train", "fine", "tune", "embed", "vector", "search",
        "rag", "retrieval", "semantic", "context", "memory", "chain",

        # LLM/GPT specific
        "claude", "gemini", "mistral", "llama", "palm", "bard",
        "openai", "anthropic", "cohere", "together", "anyscale",
        "langchain", "llamaindex", "autogen", "crew", "swarm",

        # Product types
        "tool", "kit", "suite", "platform", "studio", "work",
        "dash", "board", "panel", "console", "portal", "base",
        "cloud", "server", "host", "edge", "node", "mesh",
        "saas", "paas", "infra", "stack", "ops", "ware",

        # Business terms
        "sales", "market", "lead", "crm", "erp", "hr", "finance",
        "support", "service", "help", "desk", "ticket", "queue",
        "email", "mail", "send", "notify", "alert", "monitor",
        "onboard", "retain", "churn", "engage", "convert", "funnel",

        # Creative AI
        "art", "draw", "paint", "design", "create", "make",
        "music", "song", "sound", "compose", "beat", "mix",
        "photo", "edit", "filter", "enhance", "restore", "upscale",
        "write", "copy", "content", "blog", "article", "story",
        "midjourney", "dalle", "runway", "pika", "suno", "udio",

        # Conversational AI
        "talk", "speak", "converse", "dialog", "reply", "respond",
        "query", "answer", "faq", "knowledge", "wiki", "docs",
        "intent", "entity", "slot", "nlu", "nli", "sentiment",

        # Automation
        "automate", "workflow", "task", "job", "schedule", "trigger",
        "script", "macro", "rpa", "process", "pipeline", "chain",
        "zapier", "make", "n8n", "airflow", "prefect", "dagster",

        # Analytics
        "insight", "report", "metric", "stat", "trend", "forecast",
        "analyze", "review", "audit", "scan", "check", "test",
        "bi", "tableau", "looker", "grafana", "dash", "visual",

        # Security AI
        "secure", "guard", "protect", "shield", "safe", "trust",
        "detect", "threat", "risk", "fraud", "spam", "block",
        "soc", "siem", "xdr", "edr", "zero", "vault",

        # Healthcare AI
        "health", "medical", "clinic", "doctor", "patient", "care",
        "diagnose", "therapy", "drug", "pharma", "bio", "gene",
        "radiology", "pathology", "cardio", "neuro", "oncology",

        # Finance AI
        "trade", "invest", "stock", "crypto", "wallet", "pay",
        "bank", "loan", "credit", "budget", "expense", "invoice",
        "fintech", "defi", "nft", "web3", "blockchain", "token",

        # Education AI
        "teach", "tutor", "course", "quiz", "exam", "grade",
        "study", "note", "flash", "memory", "skill", "cert",
        "edtech", "mooc", "lms", "elearn", "upskill", "reskill",

        # E-commerce AI
        "shop", "store", "cart", "buy", "sell", "price",
        "product", "catalog", "inventory", "order", "ship", "track",
        "recommend", "personalize", "bundle", "upsell", "cross",

        # Social AI
        "social", "post", "share", "like", "follow", "connect",
        "community", "group", "team", "collab", "meet", "call",
        "influencer", "creator", "ugc", "viral", "trend", "meme",

        # Developer AI
        "git", "repo", "commit", "deploy", "ci", "cd",
        "debug", "lint", "format", "refactor", "review", "merge",
        "devops", "mlops", "aiops", "dataops", "gitops", "sre",

        # Popular name patterns
        "super", "hyper", "ultra", "mega", "max", "plus",
        "smart", "clever", "wise", "genius", "expert", "master",
        "fast", "quick", "instant", "rapid", "swift", "turbo",
        "easy", "simple", "lite", "mini", "micro", "nano",
        "open", "free", "next", "future", "new", "fresh",

        # Company suffixes/styles
        "labs", "works", "hq", "inc", "corp", "co",
        "sys", "tech", "soft", "ware", "net", "web",
        "one", "first", "prime", "alpha", "beta", "delta",

        # Vertical-specific AI
        "legal", "law", "contract", "comply", "regtech", "govtech",
        "realty", "property", "estate", "proptech", "homeby",
        "travel", "booking", "hotel", "flight", "trip", "tour",
        "food", "recipe", "meal", "kitchen", "chef", "restaurant",
        "fitness", "workout", "gym", "yoga", "meditation", "wellness",
        "fashion", "style", "outfit", "wardrobe", "trend", "beauty",

        # Emerging AI categories
        "avatar", "digital", "virtual", "ar", "vr", "xr",
        "robot", "robo", "droid", "mech", "cyber", "synth",
        "quantum", "edge", "iot", "sensor", "wearable", "smart",
        "climate", "carbon", "sustain", "green", "eco", "energy",

        # Action words
        "launch", "start", "grow", "scale", "boost", "power",
        "run", "go", "do", "get", "try", "use",
        "find", "discover", "explore", "navigate", "guide", "lead",

        # Single letter combos (often used)
        "x", "y", "z", "a", "e", "i", "o", "u",

        # Numbers (startup naming trend)
        "1", "2", "3", "10", "42", "99", "100", "360",

        # Compound patterns (high value)
        "chatgpt", "autogpt", "agentgpt", "supergpt", "turbogpt",
        "aibot", "chatbot", "voicebot", "codebot", "databot",
        "deepmind", "openapi", "huggingface", "replicate", "modal",
    ]

    def __init__(self):
        self.crt_sh_url = "https://crt.sh"
        self.max_retries = 2  # Fewer retries to avoid hammering API
        self.retry_delay = 8.0  # Longer delay between retries (increased from 5)
        self.timeout = 25.0
        self.max_concurrent = 1  # One at a time to avoid rate limiting
        self.request_delay = 6.0  # 6 seconds between requests (increased from 3)
        # Circuit breaker settings
        self.consecutive_failures = 0
        self.circuit_breaker_threshold = 3  # Stop after 3 consecutive 429s
        self.circuit_open = False

    async def query_all_sources(self, hours_back: int = 48) -> List[str]:
        """
        Query crt.sh using pattern-based discovery to find recent .ai certificates

        Args:
            hours_back: How many hours back to search

        Returns:
            Deduplicated list of discovered domains
        """
        logger.info("multi_ct_query_started", patterns=len(self.CRT_SH_PATTERNS))

        # Reset circuit breaker state for this run
        self.consecutive_failures = 0
        self.circuit_open = False

        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        all_domains: Set[str] = set()

        # Process patterns in small batches with delays to avoid rate limiting
        batch_size = self.max_concurrent
        patterns_with_results = 0
        patterns_skipped = 0

        for i in range(0, len(self.CRT_SH_PATTERNS), batch_size):
            # Circuit breaker check - stop if too many consecutive failures
            if self.circuit_open:
                patterns_skipped = len(self.CRT_SH_PATTERNS) - i
                logger.warning("circuit_breaker_open",
                             consecutive_failures=self.consecutive_failures,
                             patterns_skipped=patterns_skipped)
                break

            batch = self.CRT_SH_PATTERNS[i:i + batch_size]

            # Query this batch
            tasks = [self._query_crt_sh_pattern(pattern, cutoff_time) for pattern in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.debug("pattern_query_failed",
                               pattern=batch[j],
                               error=str(result))
                    continue
                if result:
                    patterns_with_results += 1
                    all_domains.update(result)
                    # Reset consecutive failures on success
                    self.consecutive_failures = 0

            # Delay between batches to respect rate limits
            if i + batch_size < len(self.CRT_SH_PATTERNS):
                await asyncio.sleep(self.request_delay)

        unique_domains = list(all_domains)
        logger.info("multi_ct_query_completed",
                   patterns_queried=len(self.CRT_SH_PATTERNS) - patterns_skipped,
                   patterns_skipped=patterns_skipped,
                   patterns_with_results=patterns_with_results,
                   total_unique_domains=len(unique_domains),
                   circuit_triggered=self.circuit_open)

        return unique_domains

    async def _query_crt_sh_pattern(self, pattern: str, cutoff_time: datetime) -> List[str]:
        """Query crt.sh for a single pattern (e.g., 'chat' finds chat.ai, chatbot.ai, etc.)"""
        domains = []
        query = f"{pattern}.ai"

        # Skip if circuit breaker is already open
        if self.circuit_open:
            return []

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.crt_sh_url,
                        params={"q": query, "output": "json"}
                    )

                    if response.status_code == 200:
                        # Success - reset failure counter
                        self.consecutive_failures = 0
                        data = response.json()

                        for entry in data:
                            try:
                                # Parse certificate not_before date
                                not_before_str = entry.get('not_before')
                                if not not_before_str:
                                    continue

                                cert_time = datetime.fromisoformat(
                                    not_before_str.replace('Z', '+00:00')
                                ).replace(tzinfo=None)

                                # Filter: only certificates issued in last N hours
                                if cert_time < cutoff_time:
                                    continue

                                # Extract and clean domain name
                                domain_name = entry.get('name_value', '')
                                domain = clean_domain(domain_name)

                                # Validate domain ends with .ai
                                if is_valid_domain(domain) and domain.endswith('.ai'):
                                    domains.append(domain)

                            except (ValueError, AttributeError):
                                continue

                        return list(set(domains))

                    elif response.status_code == 429:
                        # Rate limited - increment failure counter
                        self.consecutive_failures += 1
                        logger.warning("rate_limited_429",
                                     pattern=pattern,
                                     consecutive_failures=self.consecutive_failures,
                                     threshold=self.circuit_breaker_threshold)

                        # Check circuit breaker threshold
                        if self.consecutive_failures >= self.circuit_breaker_threshold:
                            self.circuit_open = True
                            logger.error("circuit_breaker_triggered",
                                       consecutive_failures=self.consecutive_failures,
                                       message="Stopping CT log queries to avoid further rate limiting")
                            return []

                        # Exponential backoff: 8s, 16s, 32s
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.debug("rate_limited_backoff", pattern=pattern, wait=wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Other error - don't retry
                        break

            except httpx.TimeoutException:
                # Timeout - try again with backoff
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                continue
            except Exception as e:
                logger.debug("pattern_query_error", pattern=pattern, error=str(e))
                break

        return list(set(domains))

    def _parse_cert_spotter(self, data: List[Dict], cutoff_time: datetime) -> List[str]:
        """Parse CertSpotter response format"""
        domains = []

        for entry in data:
            try:
                # Parse issuance time
                not_before = entry.get('not_before')
                if not not_before:
                    continue

                # CertSpotter uses Unix timestamp
                cert_time = datetime.utcfromtimestamp(not_before)

                if cert_time < cutoff_time:
                    continue

                # Extract DNS names
                dns_names = entry.get('dns_names', [])
                for domain_name in dns_names:
                    domain = clean_domain(domain_name)
                    if is_valid_domain(domain) and domain.endswith('.ai'):
                        domains.append(domain)

            except (ValueError, AttributeError, TypeError):
                continue

        return list(set(domains))
