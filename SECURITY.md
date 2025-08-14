# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within BGC-Viewer, please send an email to the maintainers. All security vulnerabilities will be promptly addressed.

**Please do not report security vulnerabilities through public GitHub issues.**

### What to include in your report

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit the issue

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on complexity, but we aim for 30 days for critical issues

## Security Measures

BGC-Viewer implements the following security measures:

- Input validation for all API endpoints
- CORS configuration for web security
- Environment-based configuration (no hardcoded secrets)
- Regular dependency updates via automated CI

## Security Best Practices for Users

When deploying BGC-Viewer:

1. Use HTTPS in production environments
2. Keep dependencies updated
3. Use environment variables for sensitive configuration
4. Run with minimal required permissions
5. Monitor logs for suspicious activity

Thank you for helping keep BGC-Viewer secure!
