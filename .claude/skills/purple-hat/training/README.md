# Training Resources

Educational resources for learning security assessment techniques.

## Structure

- `labs/` - Hands-on labs for practicing security assessments
- `ctf/` - Capture The Flag challenges
- `case-studies/` - Real-world vulnerability examples

## Getting Started

### Recommended Learning Path

1. **Start with:** Quick scan checklist
2. **Learn:** OWASP Top 10 basics
3. **Practice:** Labs on SQL injection, XSS, authentication
4. **Advanced:** LLM security, API security
5. **Master:** Full-stack security assessment

### Labs

Set up vulnerable environments to practice:

```bash
# Docker Compose vulnerable app
cd labs/
docker-compose up

# Practice assessment techniques
../scripts/quick-scan.sh
```

### CTF Challenges

Test your skills with progressively harder challenges:

```bash
# Easy challenges
cd ctf/easy/
# Medium challenges  
cd ctf/medium/
# Hard challenges
cd ctf/hard/
```

### Case Studies

Learn from real-world vulnerabilities:

```bash
# Analyze CVE examples
cd case-studies/
# Understand impact and remediation
# Apply lessons learned to your code
```

## Learning Resources

### OWASP

- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [OWASP API Security Top 10 2023](https://owasp.org/API-Security/)
- [OWASP LLM Top 10 2025](https://genai.owasp.org/llm-top-10/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)

### FastAPI Security

- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [FastAPI - Security](https://fastapi.tiangolo.com/tutorial/security/)

### Database Security

- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Engine)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)

### LLM Security

- [OWASP LLM Top 10](https://genai.owasp.org/llm-top-10/)
- [OpenAI Security Best Practices](https://openai.com/blog/chatgpt-security)
- [Prompt Injection Guide](https://promptingguide.ai/)

### Container Security

- [Docker Security](https://docs.docker.com/engine/security/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)

## Practice Targets

### Local Testing

- Start with local development environment
- Use the scripts in `../scripts/` to scan
- Practice with test payloads in `../references/test-payloads.md`

### Public Targets

- Only test on authorized systems
- Get written permission before scanning
- Use bug bounty programs (if available)
- Practice on deliberately vulnerable apps:
  - DVWA (Damn Vulnerable Web App)
  - OWASP Juice Shop
  - WebGoat

## Skill Development

### Beginner

1. Understand OWASP Top 10 risks
2. Learn to identify vulnerabilities
3. Practice with automated tools (grep, trivy)
4. Start with simple assessments

### Intermediate

1. Manual exploitation techniques
2. Complex attack chains
3. Custom script development
4. Full-stack assessments

### Advanced

1. Zero-day research
2. Advanced exploitation
3. Security architecture review
4. Threat modeling

## Community

- Participate in security forums (OWASP, Reddit r/netsec)
- Write up your findings
- Contribute to open-source tools
- Present at conferences

## Safety

**Remember:**
- Only test on authorized systems
- Report vulnerabilities responsibly
- Never use skills for malicious purposes
- Follow bug bounty disclosure policies

## Resources

- Main skill methodology: `../SKILL.md`
- Quick reference: `../QUICK-REF.md`
- Security checklists: `../references/`
- Automation scripts: `../scripts/`
