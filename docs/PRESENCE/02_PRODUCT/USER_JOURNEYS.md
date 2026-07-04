# User Journeys (v1)

## Journey 1: SMB Owner Onboarding → First Value
1. Signup (direct or via agency invite) → guided single-flow connect (GBP + Meta + WhatsApp OAuth in one sequence, NOT three separate settings pages — this is a known conversion killer in this category, test explicitly)
2. First sync completes (<15 min NFR) → dashboard shows existing reviews + connection health
3. First AI-drafted review response generated → owner reviews/approves/edits, sends (draft-then-approve flow, never auto-send without confirmation in v1 — trust-building matters more than automation purity here)
4. First WhatsApp review-request campaign sent to a recent customer list
5. Day 7: first attribution signal appears (direction-request correlation) → this is the "aha moment" the onboarding should be designed to reach as fast as possible

## Journey 2: Agency Onboarding a New Sub-Account
1. Agency logs into console → clicks "Add Client"
2. Fills minimal business info, sends the SMB owner a branded (white-label) invite link
3. SMB owner completes Journey 1 under the agency's branding
4. Agency sees the new client in their multi-client list, one-click switch to view their dashboard
5. Agency generates a consolidated cross-client report (weekly/monthly) for their own client-facing reporting

## Journey 3: Review Response Loop (daily-use core loop)
1. New review arrives (webhook/sync) → appears in Review Inbox
2. AI drafts a response (cached where the review pattern is templatable) → owner/agency approves or edits
3. Response sent → attribution engine logs the response timestamp as an input signal for correlation analysis
4. Weekly: cohort dashboard shows "businesses that respond within 24hrs saw X% higher direction-request rate" — this becomes case-study material
