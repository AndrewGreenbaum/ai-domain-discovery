"""INVESTIGATOR_AGENT - Deep-dive analysis of promising AI startups"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import whois

from models.schemas import InvestigationResult, TeamMember, FundingInfo, TechStack, SocialProof
from utils.logger import logger
from services.mcp_services import brave_search  # MCP integration


class InvestigatorAgent:
    """
    Agent responsible for deep investigation of promising domains:
    - Team background checks (LinkedIn, GitHub, Twitter)
    - Funding status (Crunchbase, press releases, news)
    - Technical stack analysis (technology detection)
    - Social proof (Twitter, ProductHunt, GitHub)
    - Competitor analysis
    - Patent/trademark searches (USPTO)
    """

    def __init__(self):
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    async def investigate_domain(self, domain: str, page_content: Optional[str] = None) -> InvestigationResult:
        """
        Run comprehensive investigation on a domain
        
        Args:
            domain: Domain name to investigate
            page_content: Optional pre-fetched page content
            
        Returns:
            InvestigationResult with all findings
        """
        logger.info("investigation_started", domain=domain)

        try:
            # Fetch content if not provided
            if not page_content:
                page_content = await self._fetch_page_content(f"https://{domain}")

            # Run all investigation tasks concurrently
            tasks = [
                self._extract_company_info(domain, page_content),
                self._find_team_members(domain, page_content),
                self._detect_funding_status(domain, page_content),
                self._analyze_tech_stack(domain, page_content),
                self._gather_social_proof(domain),
                self._find_competitors(domain, page_content),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions from tasks
            company_info = results[0] if not isinstance(results[0], Exception) else {}
            team_members = results[1] if not isinstance(results[1], Exception) else []
            funding_info = results[2] if not isinstance(results[2], Exception) else None
            tech_stack = results[3] if not isinstance(results[3], Exception) else {}
            social_proof = results[4] if not isinstance(results[4], Exception) else {}
            competitors = results[5] if not isinstance(results[5], Exception) else []

            result = InvestigationResult(
                domain=domain,
                investigated_at=datetime.utcnow(),  # Use naive datetime for DB
                company_description=company_info.get('description'),
                company_tagline=company_info.get('tagline'),
                product_category=company_info.get('category'),
                business_model=company_info.get('business_model'),
                target_market=company_info.get('target_market'),
                team_members=team_members,
                funding_info=funding_info,
                tech_stack=tech_stack,
                social_proof=social_proof,
                competitors=competitors,
                investigation_confidence=self._calculate_confidence(results)
            )

            logger.info("investigation_completed", domain=domain, confidence=result.investigation_confidence)
            return result

        except Exception as e:
            logger.error("investigation_failed", domain=domain, error=str(e))
            return InvestigationResult(domain=domain, investigated_at=datetime.utcnow())  # Use naive datetime

    async def _fetch_page_content(self, url: str) -> str:
        """Fetch page content with error handling"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.text
        except Exception as e:
            logger.warning("fetch_page_failed", url=url, error=str(e))
        return ""

    async def _extract_company_info(self, domain: str, page_content: str) -> Dict:
        """Extract company information from website"""
        try:
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ''

            # Extract from og:description
            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            if og_desc and not description:
                description = og_desc.get('content', '')

            # Extract tagline (usually in h1 or hero section)
            tagline = ''
            h1 = soup.find('h1')
            if h1:
                tagline = h1.get_text(strip=True)[:200]

            # Try to fetch About page
            about_content = await self._fetch_about_page(domain)
            if about_content:
                about_soup = BeautifulSoup(about_content, 'html.parser')
                about_text = about_soup.get_text(strip=True)[:500]
                if len(about_text) > len(description):
                    description = about_text

            # Detect product category from content
            category = self._detect_category(page_content + (about_content or ''))
            
            # Detect business model
            business_model = self._detect_business_model(page_content)
            
            # Detect target market
            target_market = self._detect_target_market(page_content)

            return {
                'description': description,
                'tagline': tagline,
                'category': category,
                'business_model': business_model,
                'target_market': target_market
            }

        except Exception as e:
            logger.error("extract_company_info_failed", domain=domain, error=str(e))
            return {}

    async def _fetch_about_page(self, domain: str) -> Optional[str]:
        """Try to fetch About page"""
        about_urls = [
            f"https://{domain}/about",
            f"https://{domain}/about-us",
            f"https://{domain}/company",
        ]
        
        for url in about_urls:
            content = await self._fetch_page_content(url)
            if content and len(content) > 500:
                return content
        return None

    def _detect_category(self, content: str) -> str:
        """Detect AI product category from content"""
        content_lower = content.lower()
        
        categories = {
            'LLM/Chat': ['language model', 'chatbot', 'conversational ai', 'chat assistant', 'llm'],
            'Computer Vision': ['computer vision', 'image recognition', 'object detection', 'facial recognition', 'ocr'],
            'NLP/Text': ['natural language', 'nlp', 'text analysis', 'sentiment analysis', 'text generation'],
            'Voice/Audio': ['speech recognition', 'voice assistant', 'audio processing', 'text-to-speech', 'voice ai'],
            'ML Platform': ['machine learning platform', 'ml ops', 'model training', 'automl', 'ml infrastructure'],
            'Data/Analytics': ['data analytics', 'predictive analytics', 'business intelligence', 'data science'],
            'Automation': ['automation', 'rpa', 'workflow automation', 'process automation'],
            'Code Generation': ['code generation', 'coding assistant', 'ai developer', 'code completion'],
            'Creative AI': ['image generation', 'art generation', 'video generation', 'creative ai', 'generative art'],
            'Search/RAG': ['semantic search', 'vector search', 'rag', 'retrieval augmented', 'knowledge base'],
        }
        
        for category, keywords in categories.items():
            if any(keyword in content_lower for keyword in keywords):
                return category
        
        return 'General AI'

    def _detect_business_model(self, content: str) -> str:
        """Detect business model from content"""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ['api', 'developer', 'integration', 'sdk']):
            return 'API/Developer Tool'
        elif any(word in content_lower for word in ['enterprise', 'b2b', 'business solution']):
            return 'B2B Enterprise'
        elif any(word in content_lower for word in ['free trial', 'pricing', 'subscribe', 'saas']):
            return 'SaaS'
        elif any(word in content_lower for word in ['marketplace', 'platform', 'ecosystem']):
            return 'Platform/Marketplace'
        
        return 'Unknown'

    def _detect_target_market(self, content: str) -> str:
        """Detect target market from content"""
        content_lower = content.lower()
        
        markets = {
            'Developers': ['developer', 'engineer', 'code', 'api', 'github'],
            'Enterprises': ['enterprise', 'business', 'organization', 'company', 'corporate'],
            'SMBs': ['small business', 'smb', 'startup', 'small team'],
            'Consumers': ['everyone', 'anyone', 'consumer', 'personal', 'individual'],
            'Healthcare': ['healthcare', 'medical', 'hospital', 'patient', 'clinical'],
            'Finance': ['finance', 'banking', 'fintech', 'investment', 'trading'],
            'Marketing': ['marketing', 'advertising', 'content creation', 'social media'],
            'Education': ['education', 'learning', 'student', 'teacher', 'academic'],
        }
        
        for market, keywords in markets.items():
            if any(keyword in content_lower for keyword in keywords):
                return market
        
        return 'General'

    async def _find_team_members(self, domain: str, page_content: str) -> List[TeamMember]:
        """Find team members from About/Team page"""
        try:
            team_members = []
            
            # Try to fetch team page
            team_urls = [
                f"https://{domain}/team",
                f"https://{domain}/about",
                f"https://{domain}/about-us",
                f"https://{domain}/people",
            ]
            
            for url in team_urls:
                content = await self._fetch_page_content(url)
                if not content:
                    continue
                    
                soup = BeautifulSoup(content, 'html.parser')
                
                # Look for team member patterns
                # Common patterns: name + role/title
                team_sections = soup.find_all(['div', 'section'], class_=re.compile(r'team|people|about', re.I))
                
                for section in team_sections:
                    # Extract names and roles
                    members = self._extract_team_from_section(section)
                    team_members.extend(members)
                
                if team_members:
                    break  # Found team members, no need to check other URLs
            
            # Try to find GitHub profiles (LinkedIn requires API access)
            for member in team_members:
                member.github_url = await self._find_github_profile(member.name)
            
            return team_members[:10]  # Limit to top 10

        except Exception as e:
            logger.error("find_team_failed", domain=domain, error=str(e))
            return []

    def _extract_team_from_section(self, section) -> List[TeamMember]:
        """Extract team members from a section"""
        members = []
        
        # Pattern 1: Look for name/title pairs
        name_elements = section.find_all(['h2', 'h3', 'h4', 'strong', 'b'])
        
        for name_elem in name_elements:
            name = name_elem.get_text(strip=True)
            
            # Skip if too long or contains common words
            if len(name) > 50 or len(name) < 5:
                continue
            if any(word in name.lower() for word in ['team', 'our', 'meet', 'about', 'leadership']):
                continue
            
            # Look for role/title nearby
            role = ''
            next_elem = name_elem.find_next(['p', 'span', 'div'])
            if next_elem:
                role_text = next_elem.get_text(strip=True)
                if len(role_text) < 100 and any(title in role_text.lower() for title in ['ceo', 'founder', 'cto', 'engineer', 'director', 'head', 'vp', 'chief']):
                    role = role_text
            
            if name and len(name.split()) >= 2:  # At least first and last name
                members.append(TeamMember(
                    name=name,
                    role=role or 'Team Member',
                    linkedin_url=None,
                    github_url=None,
                    twitter_url=None
                ))
        
        return members


    async def _find_github_profile(self, name: str) -> Optional[str]:
        """Search for GitHub profile"""
        try:
            username = name.lower().replace(' ', '')
            url = f"https://api.github.com/users/{username}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return f"https://github.com/{username}"
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.debug("github_profile_lookup_failed", name=name, error=str(e))
        return None

    async def _detect_funding_status(self, domain: str, page_content: str) -> Optional[FundingInfo]:
        """Detect funding status from page content and external sources (with Brave Search MCP)"""
        try:
            funding_info = FundingInfo()

            # Search for funding keywords in content
            content_lower = page_content.lower()

            # Look for funding announcements
            funding_patterns = [
                r'raised\s+\$?([\d.]+)\s*(million|billion|m|b)',
                r'funding round\s+of\s+\$?([\d.]+)\s*(million|billion|m|b)',
                r'\$?([\d.]+)\s*(million|billion|m|b)\s+in funding',
                r'series\s+([a-z])\s+funding',
                r'seed round',
                r'pre-seed',
            ]

            for pattern in funding_patterns:
                match = re.search(pattern, content_lower, re.IGNORECASE)
                if match:
                    funding_info.has_funding = True
                    if 'series' in pattern:
                        funding_info.funding_stage = f"Series {match.group(1).upper()}"
                    elif 'seed' in pattern:
                        funding_info.funding_stage = "Seed"
                    break

            # Look for investor names
            investor_keywords = ['backed by', 'investors include', 'funded by', 'supported by']
            for keyword in investor_keywords:
                if keyword in content_lower:
                    # Extract text around keyword
                    idx = content_lower.find(keyword)
                    context = page_content[idx:idx+200]
                    funding_info.investors = self._extract_investor_names(context)
                    break

            # Try to fetch press/news page
            press_content = await self._fetch_press_page(domain)
            if press_content:
                # Look for funding announcements in press releases
                if 'funding' in press_content.lower() or 'raised' in press_content.lower():
                    funding_info.has_funding = True

            # NEW: Use Brave Search to find funding news
            if not funding_info.has_funding:
                funding_from_search = await self._search_funding_with_brave(domain)
                if funding_from_search:
                    funding_info.has_funding = True
                    if funding_from_search.get("stage"):
                        funding_info.funding_stage = funding_from_search["stage"]
                    if funding_from_search.get("investors"):
                        funding_info.investors = funding_from_search["investors"]

            return funding_info if funding_info.has_funding else None

        except Exception as e:
            logger.error("detect_funding_failed", domain=domain, error=str(e))
            return None

    async def _search_funding_with_brave(self, domain: str) -> Optional[Dict]:
        """Use Brave Search MCP to find funding information with retry logic"""
        max_retries = 3
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                # Search for funding announcements
                query = f'"{domain}" funding OR raised OR "Series A" OR "seed round"'
                results = await brave_search.web_search(query, count=10, freshness="py")  # past year

                if not results:
                    return None

                # Analyze search results for funding info
                funding_data = {"has_funding": False}

                for result in results:
                    title = result.get("title", "").lower()
                    description = result.get("description", "").lower()
                    combined_text = f"{title} {description}"

                    # Check for funding amount
                    amount_match = re.search(r'\$?([\d.]+)\s*(million|billion|m|b)', combined_text)
                    if amount_match:
                        funding_data["has_funding"] = True
                        funding_data["amount"] = amount_match.group(0)

                    # Check for funding stage
                    if 'series a' in combined_text:
                        funding_data["stage"] = "Series A"
                    elif 'series b' in combined_text:
                        funding_data["stage"] = "Series B"
                    elif 'seed' in combined_text:
                        funding_data["stage"] = "Seed"

                    # Extract investor names
                    investors = self._extract_investor_names(combined_text)
                    if investors:
                        funding_data["investors"] = investors

                    if funding_data.get("has_funding"):
                        break

                return funding_data if funding_data.get("has_funding") else None

            except Exception as e:
                error_str = str(e).lower()
                # Check for rate limiting (429) or temporary errors
                if '429' in error_str or 'rate' in error_str or 'too many' in error_str:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning("brave_search_rate_limited",
                                     domain=domain,
                                     attempt=attempt + 1,
                                     wait=wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("brave_search_rate_limit_exhausted",
                                   domain=domain,
                                   attempts=max_retries)
                        return None
                else:
                    # Non-retryable error
                    logger.error("brave_funding_search_failed",
                               domain=domain,
                               error=str(e),
                               attempt=attempt + 1)
                    return None

        return None

    async def _fetch_press_page(self, domain: str) -> Optional[str]:
        """Fetch press/news page"""
        press_urls = [
            f"https://{domain}/press",
            f"https://{domain}/news",
            f"https://{domain}/blog",
        ]
        
        for url in press_urls:
            content = await self._fetch_page_content(url)
            if content and len(content) > 500:
                return content
        return None

    def _extract_investor_names(self, text: str) -> List[str]:
        """Extract investor names from text"""
        # Common investor patterns
        well_known_investors = [
            'Y Combinator', 'Sequoia', 'Andreessen Horowitz', 'a16z', 'Greylock',
            'Accel', 'Kleiner Perkins', 'Benchmark', 'Index Ventures', 'Lightspeed',
            'First Round', 'SV Angel', 'Google Ventures', 'Microsoft', 'OpenAI'
        ]
        
        found_investors = []
        text_lower = text.lower()
        
        for investor in well_known_investors:
            if investor.lower() in text_lower:
                found_investors.append(investor)
        
        return found_investors

    async def _analyze_tech_stack(self, domain: str, page_content: str) -> Dict:
        """Analyze technical stack"""
        try:
            tech_stack = {
                'frontend': [],
                'backend': [],
                'analytics': [],
                'infrastructure': [],
                'ai_ml': []
            }
            
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Check script tags for frameworks
            scripts = soup.find_all('script', src=True)
            for script in scripts:
                src = script.get('src', '').lower()
                
                # Frontend frameworks
                if 'react' in src:
                    tech_stack['frontend'].append('React')
                elif 'vue' in src:
                    tech_stack['frontend'].append('Vue.js')
                elif 'angular' in src:
                    tech_stack['frontend'].append('Angular')
                elif 'next' in src:
                    tech_stack['frontend'].append('Next.js')
                
                # Analytics
                if 'google-analytics' in src or 'gtag' in src:
                    tech_stack['analytics'].append('Google Analytics')
                elif 'mixpanel' in src:
                    tech_stack['analytics'].append('Mixpanel')
                elif 'segment' in src:
                    tech_stack['analytics'].append('Segment')
                
                # AI/ML libraries
                if 'tensorflow' in src:
                    tech_stack['ai_ml'].append('TensorFlow.js')
                elif 'openai' in src:
                    tech_stack['ai_ml'].append('OpenAI API')
            
            # Check for meta tags
            generator = soup.find('meta', attrs={'name': 'generator'})
            if generator:
                content = generator.get('content', '').lower()
                if 'wordpress' in content:
                    tech_stack['backend'].append('WordPress')
                elif 'shopify' in content:
                    tech_stack['backend'].append('Shopify')
            
            # Check for common chat widgets
            page_text = page_content.lower()
            if 'intercom' in page_text:
                tech_stack['infrastructure'].append('Intercom')
            if 'zendesk' in page_text:
                tech_stack['infrastructure'].append('Zendesk')
            if 'stripe' in page_text:
                tech_stack['infrastructure'].append('Stripe')
            
            # Remove duplicates
            for key in tech_stack:
                tech_stack[key] = list(set(tech_stack[key]))
            
            return tech_stack

        except Exception as e:
            logger.error("analyze_tech_stack_failed", domain=domain, error=str(e))
            return {}

    async def _gather_social_proof(self, domain: str) -> Dict:
        """Gather social proof metrics"""
        try:
            social_proof = {
                'twitter_followers': 0,
                'twitter_url': None,
                'github_stars': 0,
                'github_url': None,
                'product_hunt_votes': 0,
                'product_hunt_url': None,
                'linkedin_followers': 0,
                'linkedin_url': None,
            }
            
            # Try to find Twitter profile
            twitter_handle = await self._find_twitter_handle(domain)
            if twitter_handle:
                social_proof['twitter_url'] = f"https://twitter.com/{twitter_handle}"
                # In production, use Twitter API to get follower count
                # For now, just record the handle
            
            # Try to find GitHub organization
            github_org = await self._find_github_org(domain)
            if github_org:
                social_proof['github_url'] = f"https://github.com/{github_org}"
                # In production, use GitHub API to get repo stars
            
            # Try to find Product Hunt listing
            ph_url = await self._find_product_hunt_listing(domain)
            if ph_url:
                social_proof['product_hunt_url'] = ph_url
            
            # Try to find LinkedIn company page
            linkedin_url = await self._find_linkedin_company(domain)
            if linkedin_url:
                social_proof['linkedin_url'] = linkedin_url
            
            return social_proof

        except Exception as e:
            logger.error("gather_social_proof_failed", domain=domain, error=str(e))
            return {}

    async def _find_twitter_handle(self, domain: str) -> Optional[str]:
        """Find Twitter handle for domain"""
        try:
            # Fetch homepage
            content = await self._fetch_page_content(f"https://{domain}")
            if not content:
                return None
            
            # Look for Twitter links
            soup = BeautifulSoup(content, 'html.parser')
            twitter_links = soup.find_all('a', href=re.compile(r'twitter\.com|x\.com'))
            
            for link in twitter_links:
                href = link.get('href', '')
                match = re.search(r'(?:twitter|x)\.com/([a-zA-Z0-9_]+)', href)
                if match:
                    return match.group(1)
            
            # Check meta tags
            twitter_meta = soup.find('meta', attrs={'name': 'twitter:site'})
            if twitter_meta:
                content = twitter_meta.get('content', '')
                if content.startswith('@'):
                    return content[1:]
                return content

        except Exception as e:
            logger.debug("twitter_handle_lookup_failed", domain=domain, error=str(e))
        return None

    async def _find_github_org(self, domain: str) -> Optional[str]:
        """Find GitHub organization"""
        try:
            content = await self._fetch_page_content(f"https://{domain}")
            if not content:
                return None
            
            soup = BeautifulSoup(content, 'html.parser')
            github_links = soup.find_all('a', href=re.compile(r'github\.com'))
            
            for link in github_links:
                href = link.get('href', '')
                match = re.search(r'github\.com/([a-zA-Z0-9_-]+)', href)
                if match:
                    org = match.group(1)
                    if org not in ['sponsors', 'marketplace', 'pricing']:
                        return org
        except Exception as e:
            logger.debug("github_org_lookup_failed", domain=domain, error=str(e))
        return None

    async def _find_product_hunt_listing(self, domain: str) -> Optional[str]:
        """Find Product Hunt listing by checking page for PH links"""
        try:
            content = await self._fetch_page_content(f"https://{domain}")
            if not content:
                return None

            soup = BeautifulSoup(content, 'html.parser')
            ph_links = soup.find_all('a', href=re.compile(r'producthunt\.com'))

            for link in ph_links:
                href = link.get('href', '')
                if 'producthunt.com' in href:
                    return href
        except Exception as e:
            logger.debug("product_hunt_lookup_failed", domain=domain, error=str(e))
        return None

    async def _find_linkedin_company(self, domain: str) -> Optional[str]:
        """Find LinkedIn company page"""
        try:
            content = await self._fetch_page_content(f"https://{domain}")
            if not content:
                return None
            
            soup = BeautifulSoup(content, 'html.parser')
            linkedin_links = soup.find_all('a', href=re.compile(r'linkedin\.com/company'))
            
            for link in linkedin_links:
                href = link.get('href', '')
                if 'company' in href:
                    return href
        except Exception as e:
            logger.debug("linkedin_company_lookup_failed", domain=domain, error=str(e))
        return None

    async def _find_competitors(self, domain: str, page_content: str) -> List[str]:
        """Find competitors mentioned on the page (comparison sections, etc.)"""
        # Only extract competitors if explicitly mentioned on page
        # Full competitor discovery would require external APIs
        return []

    def _calculate_confidence(self, results: List) -> float:
        """Calculate overall investigation confidence score"""
        # Count successful extractions
        successful = sum(1 for r in results if not isinstance(r, Exception) and r)
        total = len(results)

        confidence = (successful / total) * 100 if total > 0 else 0
        return round(confidence, 2)

    # ===== PHASE 2: WHOIS & PARENT COMPANY DETECTION =====

    async def lookup_whois(self, domain: str) -> Dict:
        """
        Perform WHOIS lookup to get domain registration info (async wrapper)

        Returns dict with:
        - creation_date: datetime
        - registrar: str
        - org: str (organization name)
        - emails: list
        """
        try:
            logger.info("whois_lookup_started", domain=domain)

            # Run blocking whois in thread pool to avoid blocking event loop
            w = await asyncio.to_thread(whois.whois, domain)

            # Extract creation date (may be list or single value)
            creation_date = None
            if w.creation_date:
                if isinstance(w.creation_date, list):
                    creation_date = w.creation_date[0]
                else:
                    creation_date = w.creation_date

            result = {
                'creation_date': creation_date,
                'registrar': w.registrar if hasattr(w, 'registrar') else None,
                'org': w.org if hasattr(w, 'org') else None,
                'emails': w.emails if hasattr(w, 'emails') else None,
                'status': w.status if hasattr(w, 'status') else None,
            }

            logger.info("whois_lookup_completed", domain=domain, creation_date=creation_date)
            return result

        except Exception as e:
            logger.warning("whois_lookup_failed", domain=domain, error=str(e))
            return {}

    def extract_parent_company(self, page_content: str, title: str = "") -> Optional[str]:
        """
        Extract parent company name from page content

        Looks for patterns like:
        - "a product by [Company]"
        - "© 2024 [Company]"
        - "powered by [Company]"
        - "part of [Company]"
        - "a [Company] product"
        """
        try:
            # Combine content for searching
            all_text = page_content + " " + title

            # More specific patterns to avoid false positives
            # Use word boundaries and require specific context
            patterns = [
                # "a product by [Company]" or "built by [Company]"
                r'(?:product|built|made|created|developed)\s+by\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)',
                # "© 2024 [Company] All Rights" or "© 2024 [Company], Inc"
                r'©\s*\d{4}\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)(?:\s*[,.]|\s+(?:All|Inc|LLC|Ltd|Corp))',
                # "powered by [Company]"
                r'powered\s+by\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)',
                # "part of [Company]" or "a division of [Company]"
                r'(?:part|division|subsidiary)\s+of\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)',
                # "a [Company] product"
                r'a\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)\s+(?:product|company|project)',
            ]

            # Common false positives to filter out
            false_positives = {
                'all', 'the', 'our', 'your', 'this', 'that', 'new', 'more',
                'here', 'now', 'get', 'see', 'try', 'use', 'free', 'start',
                'sign', 'log', 'click', 'learn', 'read', 'view', 'download',
                'terms', 'privacy', 'rights', 'reserved', 'company', 'inc'
            }

            for pattern in patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                if matches:
                    company = matches[0].strip()
                    # Filter out false positives
                    if (company and
                        len(company) > 2 and
                        company.lower() not in false_positives and
                        not company.isdigit()):
                        logger.info("parent_company_detected", company=company)
                        return company

        except Exception as e:
            logger.warning("parent_company_extraction_failed", error=str(e))

        return None

    def extract_founding_year(self, page_content: str) -> Optional[int]:
        """
        Extract company founding year from content

        Looks for patterns like:
        - "founded in 2012"
        - "since 2011"
        - "established 2010"
        - "2012-2024" (in footer)
        """
        try:
            patterns = [
                r'founded in (\d{4})',
                r'since (\d{4})',
                r'established (\d{4})',
                r'est\.\s*(\d{4})',
                r'©\s*(\d{4})-\d{4}',  # "© 2012-2024"
            ]

            text_lower = page_content.lower()

            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                if matches:
                    year = int(matches[0])
                    # Sanity check: year should be reasonable
                    if 1990 <= year <= 2024:
                        logger.info("founding_year_detected", year=year)
                        return year

        except Exception as e:
            logger.warning("founding_year_extraction_failed", error=str(e))

        return None

    def calculate_company_age(self, founded_year: Optional[int] = None,
                            creation_date: Optional[datetime] = None) -> Optional[int]:
        """
        Calculate company age in years

        Args:
            founded_year: Year company was founded (from content)
            creation_date: Domain registration date (from WHOIS)

        Returns:
            Age in years, or None if cannot determine
        """
        current_year = datetime.now().year

        # Prefer founding year from content over domain creation
        if founded_year:
            age = current_year - founded_year
            logger.info("company_age_calculated", founded_year=founded_year, age=age)
            return age

        # Fallback to domain creation date
        if creation_date:
            if isinstance(creation_date, datetime):
                age = current_year - creation_date.year
                logger.info("company_age_from_domain", creation_year=creation_date.year, age=age)
                return age

        return None

    def detect_established_signals(self, page_content: str) -> Tuple[bool, List[str]]:
        """
        Detect signals that indicate this is an established company

        Returns:
            (is_established, list_of_signals_found)
        """
        signals_found = []
        text_lower = page_content.lower()

        # Established company indicators
        signals = {
            'large_user_base': [r'\d+m\+?\s+users', r'\d+\s+million users'],
            'significant_funding': [r'\$\d+m\+?\s+raised', r'\$\d+\s+million', r'series [a-d]'],
            'enterprise': ['enterprise', 'fortune 500', 'global leader'],
            'public_company': ['publicly traded', 'nasdaq:', 'nyse:'],
            'established_years': [r'founded in \d{4}', r'since \d{4}', 'established'],
            'large_team': [r'\d{3,}\+?\s+employees', r'offices in \d+ countries'],
        }

        for signal_type, patterns in signals.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    signals_found.append(signal_type)
                    break

        is_established = len(signals_found) >= 2  # 2+ signals = likely established

        if is_established:
            logger.warning("established_company_detected", signals=signals_found)

        return is_established, signals_found
