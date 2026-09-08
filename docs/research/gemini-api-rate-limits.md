# Gemini API per-minute rate limits

Researched on 2026-09-08 against Google's current Gemini Developer API documentation.

## Answer

Yes. The Gemini Developer API normally enforces requests per minute (RPM) and input tokens per minute (TPM), as well as requests per day (RPD). Exceeding any one of these limits can trigger a rate-limit error.

There is no single RPM value for every Gemini request. The active limit depends on the model or model variant and the Google Cloud project's usage tier. Google also says preview and experimental models have more restrictive limits. Image-generation models can have an images-per-minute limit, and some models can have a tokens-per-day limit.

The limits apply per Google Cloud project, not per API key. Multiple keys attached to the same project share its allowance.

## How to find the exact limit

Sign in to [Google AI Studio's Rate Limit page](https://aistudio.google.com/rate-limit) and select the project. Google directs users there for the active RPM, TPM, and daily values because limits update as the project's tier and account status change.

The public documentation no longer provides a complete static table for ordinary interactive requests. Its example of 20 RPM only explains how enforcement works; it is not a default or guaranteed limit. Google also warns that specified limits are not guaranteed and actual capacity can vary.

The project's usage tier can be checked on the [AI Studio Projects page](https://aistudio.google.com/app/projects). Current tiers are Free, Tier 1, Tier 2, and Tier 3. Tier 1 requires an active billing account. Tier 2 requires $100 paid and three days since the first successful payment. Tier 3 requires $1,000 paid and 30 days since the first successful payment.

## Separate spend-rate limit

Paid projects may also have a spend-based rate limit evaluated over a rolling 10-minute window. The documented limits are $10 for Tier 1, $50 for Tier 2, and $200 for Tier 3. Hitting this limit can return `429 RESOURCE_EXHAUSTED` even when the RPM allowance has not been exhausted.

## Primary source

- [Gemini API rate limits, Google AI for Developers](https://ai.google.dev/gemini-api/docs/rate-limits), last updated 2026-09-02 UTC. This source documents the rate-limit dimensions, per-project scope, model and tier variation, usage tiers, spend-rate limits, and the AI Studio link for active limits.
