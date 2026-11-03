# Vision Document: GreatSchools Guided Agent

## Hackathon Context

- Build in an empty AWS sandbox account. No access to GreatSchools' environment.
- Greenfield. Mirror patterns from GreatSchools' platform without integrating with it.
- Data must be synthetic, mocked, or already publicly available.
- Focus is **Level 2: the Guided Agent**. Level 3 is a stretch goal.

## Executive Summary

GreatSchools is a 25+ year national nonprofit and one of the most widely used school-information platforms in the US, with 150,000+ school profiles and 850,000+ community reviews, used by ~40M families a year. Its mission has always been to give parents the information they need to make the best education decision. Guided Search is the next step: an LLM-powered, agentic experience that supports a parent's whole K-12 journey. It turns their needs, whether stated or anticipated, into educational resources (schools, programs, parenting content) and shows how to pay for them (scholarships, public funding).

This hackathon builds the Level 2 Guided Agent: it takes a parent's initial search, asks clarifying questions, investigates on their behalf, and returns ranked, explained results.

## Business Context

### Problem Statement

School choice has become a maze: public, charter, private, and microschools; vouchers, ESAs, and tax-credit scholarships; libraries, tutoring, and career pathways. Today's tools have parents filter by blunt criteria (location, grade level, test scores) instead of searching across everything that's known, and they assume parents already know what those criteria mean. Families with resources lean on their own networks and knowledge. Lower-income families face a lasting information gap, and because family satisfaction with school choice is linked to better outcomes for kids, the families with the least access to clear information lose the most. GreatSchools already has the data. The problem is that a parent has to know the right terms and filters to reach it.

The core challenge: **move parents from a narrow, one-time "search" into an "explore" mode** where they ask questions, learn more about education, and find options that match their better-informed criteria.

### Why Now

- Choice keeps expanding: microschools, more charter schools, and an à la carte approach to education funded by state money.
- A federal tax credit takes effect in 2027, adding more money and more options.
- GreatSchools already has the scale and trust that new entrants would take years to build.
- A live proof point exists: the Oklahoma School Choice Hub, built with the state Department of Education.

### The Three-Level Framework (GreatSchools' model)

| Level | Name | What it is | Hackathon |
|-------|------|------------|-----------|
| 1 | Assistive | User drives the conversation and gets a list of matching schools with explanations | Baseline |
| 2 | **Guided Agent** | "We investigate. You decide." Agent asks clarifying questions, spots gaps, handles several query types | **Primary scope** |
| 3 | Proactive Agent | Reaches users who haven't searched: push (text, email) and on-site pull agents | Stretch |

### Target Users

The build focuses only on **parents (~90% of GreatSchools' users).**

| User | Primary Need |
|------|--------------|
| Parents | Describe needs in plain language and get guided, explained options for schools and programs |

Other stakeholders (students, realtors, teachers, school leaders, local libraries) are part of the full vision and are not in this build.

### Guiding User Journey

> A parent types a need into a single search box, e.g. "middle school in Woodstock with STEM and after-school care." The agent pulls out their criteria, asks a clarifying question ("after-school care ends at 5pm, is that workable?"), and returns ranked schools and programs. Each result shows a score and which criteria are confirmed, partial, or need the parent's attention, with evidence. The parent refines, compares two schools, and saves the ones they like to a list.

### Reference: the POC

GreatSchools' design team shared a Level 2 mockup ("Agentic Search Spectrum"). It is the best reference for the target experience. It shows:
- Extracted criteria as editable chips
- A trade-off question from the agent
- Honest handling of stale data ("that listing is from 2023, I'd hold it as a nice-to-have")
- An "I checked this for you" evidence callout
- Ranked school cards with per-criterion confirmed / partial / needs-attention breakdowns

The agent chooses the output format. The UI does not fix it.

---

## MVP Scope: Level 2 Guided Agent

### Objective

Show that a parent starting from one search + ask box can be guided by an agent, through clarifying questions and investigation, into an exploration that returns ranked, evidence-backed school and program matches and ends with the parent saving schools to a list.

### Ranked Priorities

Build in this order. If time runs out, stop at the last item that's finished.

| Priority | Capability | Description |
|----------|------------|-------------|
| **P1** | Clarify and expand the query | Single search + ask entry. Agent extracts criteria (require / prefer / avoid), asks clarifying questions, spots gaps, and returns ranked results with evidence for each criterion |
| **P2** | Compare two schools | "Compare these two" produces a generated side-by-side comparison |
| **P3** | Pull detail from a school profile | Surface and explain the detailed data inside a specific school's profile |
| **P4** | Content / framework Q&A | Answer questions using GreatSchools content and its school-quality framework, and define terms (e.g., "CTE") |

### In Scope

- One entry point that handles both search-style queries and conversational asks
- Criteria extraction shown as editable chips
- Clarifying and trade-off questions from the agent
- Ranked school and program cards with evidence per criterion
- Save schools to a list (the end of the core journey)
- Thumbs up / down relevance feedback on results

### Out of Scope

- Level 3 proactive engagement (text/email push, pull agents)
- Login and accounts. Assume the user is signed in.
- Real GreatSchools data or any student data

### Stretch Goals

- **Capture the parent's final choice.** School choice includes in-person visits and research outside the site. After saving schools, the agent follows up to learn which school the parent chose, why they chose it, and asks for feedback on the journey so far (a first review).
- **Level 3 preview:** how to engage parents who haven't started a search.

### Success Looks Like

- [ ] A parent can go from a plain-language query to ranked, explained results (P1)
- [ ] The agent asks at least one useful clarifying or trade-off question
- [ ] Each result shows which criteria are confirmed, partial, or need attention, with evidence
- [ ] The agent flags missing or stale data instead of guessing
- [ ] The parent can save schools to a list

GreatSchools' real-world metrics, for context:
- **Primary:** saves-to-searches ratio
- **Secondary:** result relevance (thumbs up / down) and number of criteria captured per search

---

## Risks and Open Questions

### Risks

| Risk | Mitigation |
|------|------------|
| Scope creep beyond P1 | Follow the ranked priorities; get P1 working end to end first |
| "Explore mode" feels vague to build | Use the POC as the concrete reference |
| Answers sound confident but are wrong | Show evidence with every result; flag stale or missing data |

### Open Questions

- [ ] Sample OpenSearch documents and data feeds from GreatSchools (promised; a starter synthetic dataset is provided in the meantime)
