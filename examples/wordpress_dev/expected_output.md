# WordPress Fixture — Expected Output Reference

This file captures the hand-written expected output from the user's spec.
The engine is evaluated by comparing its output against this reference.

## Expected Central Entity

- **Primary:** WordPress Website Development Services
- **Supporting:** WordPress Security & Performance Optimization
- **Source Context:** "Affordable enterprise-grade WordPress development and security services optimized for SEO, speed, and business growth."

## Expected Pillars (10 total)

1. WordPress Website Development Services (commercial, priority 1)
2. WordPress Security Services (commercial, priority 1)
3. WordPress Speed Optimization Services (commercial, priority 1)
4. Elementor Website Development (commercial, priority 1)
5. SEO-Friendly WordPress Development (commercial, priority 2)
6. Enterprise WordPress Solutions (commercial, priority 2)
7. WordPress Maintenance Services (commercial, priority 3)
8. WooCommerce Website Development (commercial, priority 2)
9. WordPress Firewall Setup Services (commercial, priority 1)
10. Website Redesign Services (commercial, priority 3)

Plus 2 geographic pillars implied by USA + Europe targeting.

## Expected Clusters (sampled — see spec for full list)

### Under WordPress Development pillar
- Custom WordPress Website Development
- Responsive WordPress Design
- Mobile-Optimized WordPress Websites
- Small Business WordPress Websites
- Startup Website Development
- Blog Website Development
- Corporate WordPress Websites
- Landing Page Development
- SEO Website Architecture

### Under Performance Optimization pillar
- Core Web Vitals Optimization
- WordPress Caching Setup
- Image Optimization
- CDN Setup for WordPress
- Database Optimization
- Hosting Optimization
- Mobile Speed Optimization
- JavaScript & CSS Optimization

### Under Security pillar
- WordPress Firewall Setup
- Malware Protection
- Login Security
- WordPress Hardening
- SSL Setup
- Two-Factor Authentication
- Backup Systems

## Evaluation Criteria

When evaluating stage 3 output against this reference, score:

| Criterion | Pass threshold |
|-----------|---------------|
| Engine identifies "WordPress Website Development Services" or near-equivalent as central entity | Required |
| Engine generates 8-12 pillars total | Required |
| Engine matches at least 7 of the 10 reference pillars (allow synonym variations) | 70% |
| Engine generates 6-10 clusters per pillar | Required |
| Cluster overlap with reference is 60%+ for the matched pillars | 60% |
| Priority 1 pillars include "Website builds" and "Speed optimization" related entities | Required |
| At least 60% of pillars are commercial intent | Required |
