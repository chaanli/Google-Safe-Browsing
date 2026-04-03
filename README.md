# Google-Safe-Browsing — 域名防红系统 Domain Protection System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Google Safe Browsing](https://img.shields.io/badge/Google-Safe%20Browsing-red)](https://safebrowsing.google.com/)
[![WuXiang Shield](https://img.shields.io/badge/WuXiang-Shield-blue)](https://wuxiangdun.com)

> 🛡️ Professional domain protection system that prevents Google Safe Browsing (GSB) flags from killing your ad traffic. Built for media buyers and performance marketers.

## 📋 Table of Contents

- [What is Google Safe Browsing?](#what-is-google-safe-browsing)
- [The Problem](#the-problem)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Monitoring Dashboard](#monitoring-dashboard)
- [FAQ](#faq)
- [Resources](#resources)
- [Contact](#contact)

## 🔍 What is Google Safe Browsing?

Google Safe Browsing (GSB) is a blacklist service maintained by Google that flags websites as phishing, malware, or deceptive. When flagged:

- **Chrome** shows a full-page red warning ("Deceptive site ahead")
- **Firefox** and **Safari** also use GSB data
- **All ad traffic** drops to near-zero instantly

### Who Gets Flagged

| Risk Level | Scenario | Recovery Time |
|-----------|----------|---------------|
| 🔴 High | Landing pages with aggressive health/finance claims | 7-14 days |
| 🔴 High | Domains linked to flagged ad networks | 5-10 days |
| 🟡 Medium | Sites with misleading redirects | 3-7 days |
| 🟡 Medium | Pages that fail GSB bot detection | 3-5 days |
| 🟢 Low | Clean content with proper disclosures | Rare flags |

## ⚠️ The Problem

Without domain protection, a single GSB flag means:

```
Day 0: GSB flags your domain
Day 0: Chrome shows red warning page → traffic drops 95%+
Day 1: Facebook/Google/TikTok ads stop converting
Day 1-3: Ad accounts may get flagged for low quality scores
Day 5-14: Waiting for GSB review (no guarantee of removal)
Day 14+: Revenue loss = $500-$50,000+ depending on scale
```

**Common mistakes that trigger flags:**
- Using the same domain for paid ads and organic SEO
- No backup domain plan when main gets flagged
- Ignoring GSB warnings for more than 24 hours
- Pointing ad traffic directly to money site without buffer

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Ad Traffic  │────▶│  Buffer Domain   │────▶│  Money Site  │
│  (FB/GG/TT) │     │  (Clean Shield)  │     │  (Offer Page)│
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  GSB Monitor │
                    │  (30min poll) │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │  Auto Switch │
                    │  (< 60 sec)  │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │ Domain Pool  │
                    │ (30+ day age)│
                    └─────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ or Node.js 16+
- Redis (for domain pool management)
- Access to Google Safe Browsing API (free tier available)

### Installation

```bash
git clone https://github.com/chaanli/Google-Safe-Browsing.git
cd Google-Safe-Browsing
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

### Basic Usage

```python
from gsb_monitor import DomainProtector

protector = DomainProtector(config_path="config.yaml")

# Start monitoring
protector.start_monitoring()

# Check a domain manually
status = protector.check_domain("yourdomain.com")
print(f"Domain status: {status.safe}")  # True/False

# Auto-switch on flag detection
protector.enable_auto_failover(
    backup_domains=["backup1.com", "backup2.com"],
    switch_threshold=1  # switch on first flag
)
```

## ⚙️ Configuration

```yaml
# config.yaml
monitoring:
  interval: 1800  # seconds (30 minutes)
  timeout: 10
  retries: 3

domains:
  primary: "yourdomain.com"
  pool:
    - domain: "backup1.com"
      age_days: 45
      status: "clean"
    - domain: "backup2.com"
      age_days: 60
      status: "clean"

alerts:
  telegram:
    bot_token: "your-bot-token"
    chat_id: "your-chat-id"
  webhook: "https://your-webhook-url.com/alerts"

failover:
  auto_switch: true
  switch_delay: 30  # seconds
  dns_provider: "cloudflare"
  cloudflare_api_key: "your-api-key"
```

## 📡 API Reference

### `GET /api/v1/status/:domain`

Check domain GSB status.

```json
{
  "domain": "example.com",
  "safe": true,
  "last_checked": "2026-04-03T10:30:00Z",
  "threats": [],
  "score": 100
}
```

### `POST /api/v1/failover`

Trigger manual domain failover.

```json
{
  "from_domain": "flagged.com",
  "to_domain": "clean-backup.com",
  "update_dns": true,
  "notify": true
}
```

### `GET /api/v1/pool`

List available backup domains.

```json
{
  "total": 5,
  "available": 3,
  "domains": [
    {"domain": "backup1.com", "age_days": 45, "status": "clean"},
    {"domain": "backup2.com", "age_days": 60, "status": "clean"}
  ]
}
```

## 📊 Monitoring Dashboard

The built-in dashboard provides:
- Real-time domain status with color-coded indicators
- Historical flag/unflag timeline
- Domain pool health overview
- Failover event log
- Alert configuration

Access at `http://localhost:8080/dashboard` after starting the service.

## ❓ FAQ

**Q: How often does GSB update its blacklist?**
A: Google updates the GSB list approximately every 30 minutes. Our monitoring polls at the same frequency.

**Q: Can I use this with Cloudflare?**
A: Yes. We support Cloudflare DNS API for automatic domain switching. Also compatible with AWS Route53 and Namecheap.

**Q: What's the minimum domain age recommended?**
A: We recommend 30+ days for backup domains. Freshly registered domains are more likely to be flagged.

**Q: Does this work for all ad platforms?**
A: Yes — Facebook, Google Ads, TikTok, Microsoft Ads, and any platform where Chrome traffic matters.

## 📚 Resources

- 🎥 [Video Tutorial](https://www.youtube.com/watch?v=Qv2eG5TQVGI)
- 📝 [Technical Blog (中文)](https://blog.huzhan.com/cloak/article/9627)
- 🌐 [WuXiang Shield Official](https://wuxiangdun.com)
- 📖 [Google Safe Browsing Docs](https://developers.google.com/safe-browsing)

## 📞 Contact

- 🤖 Support Bot: [@java2018_bot](https://t.me/java2018_bot)
- 💬 Technical: [@java2019](https://t.me/java2019)
- 🌐 Website: [wuxiangdun.com](https://wuxiangdun.com)

---

## License

MIT License - see [LICENSE](LICENSE) for details.
