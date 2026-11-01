# Architecture and governance rules

This note expands Sections III and IV of the paper and explains how the reference code implements them.

## 1. The governed loop

| Step | Paper (Table II) | Reference code |
|---|---|---|
| 1 Identify | Compare the photo with passport images and propose a match | Takes the top `(object_id, confidence)` candidate. Below `min_match_confidence`, or with no passport for the object, the request takes the *unmatched* path. |
| 2 Authenticate | Check role and access rights | Role must be configured; students need recorded consent; the role's access levels filter claims. |
| 3 Retrieve | Fetch passport and approved sources | Selects claims whose topic matches the intent. Community-restricted strands are excluded. |
| 4 Verify | Check evidence, freshness, trust label | Source admission (five criteria), provenance coverage P, freshness R, curator approval H. |
| 5 Govern | Answer, refuse or escalate | Computes T, Q and A, then applies Eq. (3) in the order refuse > review > answer. |
| 6 Explain | Answer with source, label and date | Builds an attributed answer. Contested passports show every approved strand side by side. |
| 7 Audit | Log the decision and evidence | Writes one hash-chained record with the Table IV fields. |
| 8 Learn | Study cards, quizzes, curator tasks | Explore requests return the study card and quiz. Refused or reviewed requests create curator tasks. |

## 2. Seven layers and their precedence

Conflicts between layers are resolved by a fixed precedence. A later layer can never override an earlier refusal:

```
identity & access (A)  >  privacy & cultural restriction (Q)  >  provenance & evidence (T)  >  guardrails  >  delivery
```

Intersections that the tests cover:

* **Strong provenance does not license disclosure (G2 over G3).** The ritual-chamber location has T of about 0.98 but A = 0, so it is refused (`test_protected_location_refused_even_with_high_trust`).
* **Curator approval raises T but cannot lower Q.** `curator_action` records the original scores, needs a non-empty reason, and appends a separate audit record (`test_curator_override_logged_and_requires_reason`).
* **Community restriction beats role.** Even a curator never receives a community-restricted strand through the agent (`test_community_restricted_strand_never_released_even_to_curator`).
* **GDPR erasure vs. audit retention.** Audit records hold pseudonymous IDs and content hashes, not raw media (`raw_media_stored: false`), so personal data can be erased without breaking the chain.
* **Fail closed.** Any exception in the loop produces a refusal, a curator task and an audit record (`test_fail_closed`).

## 3. Contested heritage

A passport stores **interpretation strands**, each with a perspective (`museum record`, `community account`, `academic debate`, `disputed`), an attribution and its own claims. When `contested` is true and no `consensus_strand` is recorded:

* the answer presents every approved, non-restricted strand with attribution and does not merge or rank them;
* the contested-history factor B = 0.3 is added to Q;
* the label `plural-interpretations` is shown to the user.

## 4. Source admission (Section III.B)

A source is admitted only if `approval.status == "approved"` **and** all five criteria hold:

1. `traceable_provenance`
2. `scholarly_or_institutional_standing`
3. `community_consent`
4. `review_date_recorded`
5. `conflict_of_interest_checked`

Claims backed only by non-admitted sources are dropped from answers. If no claim survives, S = P = 0 and the request is refused (cases `g1-1` and `g1-3`). A withdrawn source (the 1972 guidebook) is silently excluded while the other strands are still answered (case `g1-2`).

## 5. Audit record (Table IV)

| Field group | Stored as |
|---|---|
| Request | `request_id`, UTC `time`, `channel`, `language` |
| Requester | `pseudonym`, `role`, `consent_ref` |
| Input | `type`, `content_hash`, `raw_media_stored: false` |
| Passport | `object_id`, `version`, `strands_used` |
| Sources | `source_id`, `approver_roles`, `reviewed_on`, `admitted` |
| Scores | S, P, C, R, H, T, D, U, X, B, L, Q, A |
| Decision | `action`, triggering `rule` |
| Human action | `curator_id`, `action`, `reason`, `time` (or null) |
| Output | `response_hash`, `labels`, `model_version`, `policy_version` |
| Integrity | `seq`, `prev_hash`, `hash` (SHA-256 over the canonical JSON) |

`verify_chain` detects edits, deletions and reordering (`tests/test_audit.py`).

## 6. Proportionate operation for small institutions

The schema allows a minimal passport: identity, one approved source, a review date and a sensitivity label. Only requests in the review band reach a curator, and each one becomes an item in `agent.curator_queue` that can be cleared in batches. The evaluation reports the number of curator tasks so that workload can be tracked.

## 7. Example platform mapping

| Need | Generic building block | Example Microsoft-aligned option |
|---|---|---|
| Agent orchestration | Low-code agent platform | Copilot Studio |
| Grounded retrieval | Search index | Azure AI Search |
| Passport store | Governed document library / database | Dataverse or SharePoint |
| Identity and roles | Identity and access management | Entra ID |
| Curator approvals | Approval workflow | Power Automate |
| Classification and retention | Data-governance catalog | Purview |
| Audit dashboards | Log store and dashboards | Azure Monitor or Power BI |

These products are examples. Using them does not by itself establish compliance with the EU AI Act or GDPR.
