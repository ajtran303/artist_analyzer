# SECURITY CHECKLIST

## Before Deploying to Production

### Authentication & Authorization

- [ ] Rate limiting implemented on all endpoints
- [ ] CSRF protection enabled
- [ ] Input validation on all user inputs
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS protection (sanitize HTML output)

### Secrets Management

- [ ] .env file in .gitignore
- [ ] All secrets in environment variables
- [ ] No hardcoded credentials anywhere
- [ ] Secrets never logged

### Network Security

- [ ] HTTPS enforced (redirect HTTP → HTTPS)
- [ ] Security headers set (HSTS, X-Frame-Options, etc.)
- [ ] CORS configured properly
- [ ] Redis password protected
- [ ] Database password strong

### Database Security

- [ ] Database credentials strong
- [ ] SQL injection prevention verified
- [ ] Foreign key constraints enabled

### API Security

- [ ] Rate limiting on all endpoints
- [ ] Input validation on all fields
- [ ] Error messages sanitized (no stack traces)
- [ ] Logging configured (no sensitive data)
- [ ] Genius API rate limiting respected

### Code Security

- [ ] Dependencies up to date (pip audit)
- [ ] No hardcoded passwords/tokens
- [ ] No debug mode in production
- [ ] Exception handling comprehensive
- [ ] Celery tasks secure (JSON serializer)

### Docker & Deployment

- [ ] Dockerfile uses specific base image versions
- [ ] Docker secrets used (not env vars in Dockerfile)
- [ ] Container runs as non-root user
- [ ] Resource limits set (memory, CPU)
- [ ] Health checks configured

### Testing

- [ ] All security tests passing
- [ ] Input validation tests passing
- [ ] API key tests passing
- [ ] Rate limit tests passing
- [ ] CSRF tests passing
