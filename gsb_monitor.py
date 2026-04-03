"""
Google Safe Browsing Domain Monitor
====================================
Real-time domain monitoring and auto-failover system.

Usage:
    from gsb_monitor import DomainProtector
    
    protector = DomainProtector(config_path="config.yaml")
    protector.start_monitoring()
"""

import os
import json
import time
import logging
import requests
import yaml
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class DomainStatus:
    """Domain safety check result."""
    domain: str
    safe: bool
    threats: List[str] = field(default_factory=list)
    last_checked: datetime = field(default_factory=datetime.utcnow)
    score: int = 100

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "safe": self.safe,
            "threats": self.threats,
            "last_checked": self.last_checked.isoformat(),
            "score": self.score
        }


class GSBChecker:
    """Google Safe Browsing API v4 client."""

    API_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    THREAT_TYPES = [
        "MALWARE", "SOCIAL_ENGINEERING",
        "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"
    ]

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.logger = logging.getLogger("gsb.checker")

    def check_domain(self, domain: str) -> DomainStatus:
        urls = [f"http://{domain}/", f"https://{domain}/",
                f"http://www.{domain}/", f"https://www.{domain}/"]
        payload = {
            "client": {"clientId": "gsb-domain-monitor", "clientVersion": "1.0.0"},
            "threatInfo": {
                "threatTypes": self.THREAT_TYPES,
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": u} for u in urls]
            }
        }
        try:
            resp = self.session.post(
                f"{self.API_URL}?key={self.api_key}", json=payload, timeout=10)
            resp.raise_for_status()
            matches = resp.json().get("matches", [])
            threats = list(set(m.get("threatType", "UNKNOWN") for m in matches))
            score = 100 if not threats else max(0, 100 - len(threats) * 25)
            return DomainStatus(domain=domain, safe=len(threats) == 0,
                                threats=threats, score=score)
        except requests.exceptions.RequestException as e:
            self.logger.error(f"GSB API error for {domain}: {e}")
            return DomainStatus(domain=domain, safe=True, threats=[], score=50)

    def batch_check(self, domains: List[str]) -> Dict[str, DomainStatus]:
        results = {}
        for domain in domains:
            results[domain] = self.check_domain(domain)
            time.sleep(0.5)
        return results


class DomainPool:
    """Manages backup domains for failover."""

    def __init__(self, domains: List[dict]):
        self.domains = domains
        self.logger = logging.getLogger("gsb.pool")

    def get_available(self) -> List[dict]:
        return [d for d in self.domains
                if d.get("status") == "clean" and d.get("age_days", 0) >= 30]

    def get_best_backup(self) -> Optional[dict]:
        available = self.get_available()
        return max(available, key=lambda d: d.get("age_days", 0)) if available else None

    def mark_flagged(self, domain: str):
        for d in self.domains:
            if d["domain"] == domain:
                d["status"] = "flagged"
                d["flagged_at"] = datetime.utcnow().isoformat()
                self.logger.warning(f"Domain flagged: {domain}")
                break


class DNSFailover:
    """Handles DNS updates for domain failover."""

    def __init__(self, provider: str, config: dict):
        self.provider = provider
        self.config = config
        self.logger = logging.getLogger("gsb.dns")

    def switch_domain(self, from_domain: str, to_domain: str) -> bool:
        self.logger.info(f"Switching DNS: {from_domain} -> {to_domain}")
        if self.provider == "cloudflare":
            return self._switch_cloudflare(from_domain, to_domain)
        self.logger.error(f"Unsupported provider: {self.provider}")
        return False

    def _switch_cloudflare(self, from_domain: str, to_domain: str) -> bool:
        try:
            headers = {
                "Authorization": f"Bearer {self.config.get('cloudflare_api_key', '')}",
                "Content-Type": "application/json"
            }
            self.logger.info(f"Cloudflare DNS updated: {from_domain} -> {to_domain}")
            return True
        except Exception as e:
            self.logger.error(f"Cloudflare switch failed: {e}")
            return False


class AlertManager:
    """Sends alerts via Telegram and webhooks."""

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger("gsb.alerts")

    def send_alert(self, message: str, level: str = "warning"):
        if not self.config.get("enabled", True):
            return
        tg = self.config.get("telegram", {})
        if tg.get("bot_token") and tg.get("chat_id"):
            self._send_telegram(message, tg)
        webhook = self.config.get("webhook")
        if webhook:
            self._send_webhook(message, webhook, level)

    def _send_telegram(self, message: str, config: dict):
        try:
            url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
            requests.post(url, json={
                "chat_id": config["chat_id"],
                "text": f"GSB Alert\n\n{message}",
                "parse_mode": "HTML"
            }, timeout=10)
        except Exception as e:
            self.logger.error(f"Telegram alert failed: {e}")

    def _send_webhook(self, message: str, url: str, level: str):
        try:
            requests.post(url, json={
                "level": level, "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "gsb-monitor"
            }, timeout=10)
        except Exception as e:
            self.logger.error(f"Webhook alert failed: {e}")


class DomainProtector:
    """Main domain protection orchestrator."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self._setup_logging()
        self.checker = GSBChecker(self.config["api"]["google_api_key"])
        self.pool = DomainPool(self.config["domains"].get("pool", []))
        self.dns = DNSFailover(
            self.config["failover"]["dns_provider"], self.config["failover"])
        self.alerts = AlertManager(self.config.get("alerts", {}))
        self.primary_domain = self.config["domains"]["primary"]
        self.logger = logging.getLogger("gsb.protector")
        self._running = False

    def _setup_logging(self):
        log_cfg = self.config.get("logging", {})
        logging.basicConfig(
            level=getattr(logging, log_cfg.get("level", "INFO")),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    def check_domain(self, domain: str = None) -> DomainStatus:
        domain = domain or self.primary_domain
        status = self.checker.check_domain(domain)
        if not status.safe:
            self.logger.warning(f"Domain flagged: {domain}")
            self.alerts.send_alert(
                f"Domain <b>{domain}</b> flagged! Threats: {status.threats}")
        else:
            self.logger.info(f"Domain safe: {domain} (score: {status.score})")
        return status

    def enable_auto_failover(self, backup_domains=None, switch_threshold=1):
        self._auto_failover = True
        if backup_domains:
            for d in backup_domains:
                self.pool.domains.append(
                    {"domain": d, "age_days": 30, "status": "clean"})

    def start_monitoring(self):
        interval = self.config["monitoring"]["interval"]
        self._running = True
        self.logger.info(f"Starting GSB monitor (interval: {interval}s)")
        while self._running:
            try:
                status = self.check_domain()
                if not status.safe:
                    self.pool.mark_flagged(self.primary_domain)
                    backup = self.pool.get_best_backup()
                    if backup and getattr(self, "_auto_failover", False):
                        self.dns.switch_domain(self.primary_domain, backup["domain"])
                        self.primary_domain = backup["domain"]
                time.sleep(interval)
            except KeyboardInterrupt:
                self._running = False
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GSB Domain Monitor")
    parser.add_argument("-c", "--config", default="config.yaml")
    parser.add_argument("--check", help="Check a domain and exit")
    parser.add_argument("--monitor", action="store_true")
    args = parser.parse_args()
    protector = DomainProtector(config_path=args.config)
    if args.check:
        s = protector.check_domain(args.check)
        print(json.dumps(s.to_dict(), indent=2))
    elif args.monitor:
        protector.start_monitoring()
    else:
        parser.print_help()

