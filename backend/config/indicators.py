"""
Domain validation indicator lists - patterns for detecting parking, for-sale, and coming-soon pages

These lists are used by ValidationAgent to classify domains.
Update these lists to improve detection accuracy.
"""

# Parking page indicators - patterns that suggest a domain is parked
PARKING_INDICATORS = [
    # Generic parking
    "domain registered on",
    "this domain was just registered",
    "coming soon",
    "under construction",
    "domain for sale",
    "just purchased",
    "website launching soon",
    "default web page",
    "future home",
    "parked domain",
    "buy this domain",
    "domain is for sale",
    "is this domain name yours",
    "sign in to manage your domain",
    "domain name registration",
    "register your domain name",

    # Registrar defaults
    "welcome to nginx",
    "apache default page",
    "it works!",
    "default server page",
    "web server is working",
    "successfully installed",
    "test page",
    "placeholder page",

    # Generic templates
    "lorem ipsum",
    "your website here",
    "coming soon template",
    "bootstrap template",
    "html template",
    "website template",

    # Monetization parking
    "related searches",
    "sponsored listings",
    "click here for",
    "advertisement",
    "related links",
]

# Real "coming soon" indicators - legitimate pre-launch pages
REAL_COMING_SOON_INDICATORS = [
    "launching in",
    "join our waitlist",
    "early access",
    "sign up for updates",
    "follow us on",
    "beta access",
    "notify me",
]

# For sale indicators - patterns that suggest domain is being sold
FOR_SALE_INDICATORS = [
    # Direct sale phrases
    "buy this domain",
    "domain for sale",
    "purchase this domain",
    "make an offer",
    "inquire about this domain",
    "domain is for sale",
    "this domain is for sale",
    "buy now",
    "domain available for purchase",
    "acquire this domain",
    "own this domain",
    "instant ownership transfer",

    # Marketplace platforms
    "porkbun marketplace",
    "porkbun.com",
    "sedo.com",
    "sedo marketplace",
    "godaddy domain",
    "godaddy auctions",
    "afternic.com",
    "dan.com",
    "flippa.com",
    "namecheap marketplace",
    "squadhelp",
    "brandpa",
    "brandroot",
    "atom.com",
    "undeveloped.com",

    # Domain parking services
    "parked by",
    "parked domain",
    "domain parking",
    "bodis.com",
    "above.com",
    "domain sponsor",
    "smartname",

    # Sale-specific content
    "price upon request",
    "contact owner",
    "domain inquiry",
    "lease this domain",
    "monthly payment",
    "escrow.com",
    "buyer protection",
    "secure transaction",
    "payment plan available",
    "financed domain",
]
