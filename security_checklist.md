# Day 7 Support Bot Security Checklist

| Risk | Evidence | Severity | OWASP Category | Fix | Status |
|---|---|---|---|---|---|
| Hardcoded API key | API key present in source code | High | A02 Cryptographic Failures | Use environment variables | Fixed |
| Unauthorized refunds | AI could trigger refund tool | High | A01 Broken Access Control | Validate order and amount; require human approval | Fixed |
| Unauthorized account deletion | AI could delete customer accounts | High | A01 Broken Access Control | Require human approval | Fixed |
| Prompt injection | User can manipulate AI instructions | High | A04 Insecure Design | Validate actions independently of AI responses | Mitigated |
| Sensitive data in logs | Customer details included in logs | High | A09 Security Logging and Monitoring Failures | Log request IDs and metadata only | Fixed |
| Invalid input | Invalid emails and messages accepted | Medium | A04 Insecure Design | Validate input and limit message length | Fixed |
| Unknown order handling | Invalid order IDs | Medium | A04 Insecure Design | Return safe error message | Fixed |
| Debug mode | Debug server may expose information | High | A05 Security Misconfiguration | Disable debug mode | Fixed |
| Missing AI monitoring | No latency/token/cost monitoring | Medium | A09 Security Logging and Monitoring Failures | Add monitoring logs | Fixed |

## Summary

The Support Bot was reviewed for input validation, unauthorized actions, prompt injection, sensitive logging, hardcoded credentials, and monitoring.

Security improvements were implemented and verified using automated tests and API testing.
