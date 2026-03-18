## When to use this skill
To write internal communications, use this skill for:
- 3P updates (Progress, Plans, Problems)
- Company newsletters
- FAQ responses
- Status reports
- Leadership updates
- Project updates
- Incident reports

## How to use this skill

To write any internal communication:

1. **Identify the communication type** from the request
2. **Load the appropriate guideline file** from the `examples/` directory:
    - `examples/3p-updates.md` - For Progress/Plans/Problems team updates
    - `examples/company-newsletter.md` - For company-wide newsletters
    - `examples/faq-answers.md` - For answering frequently asked questions
    - `examples/general-comms.md` - For anything else that doesn't explicitly match one of the above
3. **Follow the specific instructions** in that file for formatting, tone, and content gathering

If the communication type doesn't match any existing guideline, ask for clarification or more context about the desired format.

## Keywords
3P updates, company newsletter, company comms, weekly update, faqs, common questions, updates, internal comms


---

## Supporting Code, Schemas, and Documentation

Extracted from 5 supporting files (0 Python, 0 JSON, 0 YAML, 5 docs). 0 binary files skipped.

### Document: 3p-updates.md

## Instructions
You are being asked to write a 3P update. 3P updates stand for "Progress, Plans, Problems." The main audience is for executives, leadership, other teammates, etc. They're meant to be very succinct and to-the-point: think something you can read in 30-60sec or less. They're also for people with some, but not a lot of context on what the team does.

3Ps can cover a team of any size, ranging all the way up to the entire company. The bigger the team, the less granular the tasks should be. For example, "mobile team" might have "shipped feature" or "fixed bugs," whereas the company might have really meaty 3Ps, like "hired 20 new people" or "closed 10 new deals." 

They represent the work of the team across a time period, almost always one week. They include three sections:
1) Progress: what the team has accomplished over the next time period. Focus mainly on things shipped, milestones achieved, tasks created, etc.
2) Plans: what the team plans to do over the next time period. Focus on what things are top-of-mind, really high priority, etc. for the team.
3) Problems: anything that is slowing the team down. This could be things like too few people, bugs or blockers that are preventing the team from moving forward, some deal that fell through, etc.

Before writing them, make sure that you know the team name. If it's not specified, you can ask explicitly what the team name you're writing for is.


## Tools Available
Whenever possible, try to pull from available sources to get the information you need:
- Slack: posts from team members with their updates - ideally look for posts in large channels with lots of reactions
- Google Drive: docs written from critical team members with lots of views
- Email: emails with lots of responses of lots of content that seems relevant
- Calendar: non-recurring meetings that have a lot of importance, like product reviews, etc.


Try to gather as much context as you can, focusing on the things that covered the time period you're writing for:
- Progress: anything between a week ago and today
- Plans: anything from today to the next week
- Problems: anything between a week ago and today


If you don't have access, you can ask the user for things they want to cover. They might also include these things to you directly, in which case you're mostly just formatting for this particular format.

## Workflow

1. **Clarify scope**: Confirm the team name and time period (usually past week for Progress/Problems, next
week for Plans)
2. **Gather information**: Use available tools or ask the user directly
3. **Draft the update**: Follow the strict formatting guidelines
4. **Review**: Ensure it's concise (30-60 seconds to read) and data-driven

## Formatting

The format is always the same, very strict formatting. Never use any formatting other than this. Pick an emoji that is fun and captures the vibe of the team and update.

[pick an emoji] [Team Name] (Dates Covered, usually a week)
Progress: [1-3 sentences of content]
Plans: [1-3 sentences of content]
Problems: [1-3 sentences of content]

Each section should be no more than 1-3 sentences: clear, to the point. It should be data-driven, and generally include metrics where possible. The tone should be very matter-of-fact, not super prose-heavy.

### Document: company-newsletter.md

## Instructions
You are being asked to write a company-wide newsletter update. You are meant to summarize the past week/month of a company in the form of a newsletter that the entire company will read. It should be maybe ~20-25 bullet points long. It will be sent via Slack and email, so make it consumable for that.

Ideally it includes the following attributes:
- Lots of links: pulling documents from Google Drive that are very relevant, linking to prominent Slack messages in announce channels and from executives, perhgaps referencing emails that went company-wide, highlighting significant things that have happened in the company.
- Short and to-the-point: each bullet should probably be no longer than ~1-2 sentences
- Use the "we" tense, as you are part of the company. Many of the bullets should say "we did this" or "we did that"

## Tools to use
If you have access to the following tools, please try to use them. If not, you can also let the user know directly that their responses would be better if they gave them access.

- Slack: look for messages in channels with lots of people, with lots of reactions or lots of responses within the thread
- Email: look for things from executives that discuss company-wide announcements
- Calendar: if there were meetings with large attendee lists, particularly things like All-Hands meetings, big company announcements, etc. If there were documents attached to those meetings, those are great links to include.
- Documents: if there were new docs published in the last week or two that got a lot of attention, you can link them. These should be things like company-wide vision docs, plans for the upcoming quarter or half, things authored by critical executives, etc.
- External press: if you see references to articles or press we've received over the past week, that could be really cool too.

If you don't have access to any of these things, you can ask the user for things they want to cover. In this case, you'll mostly just be polishing up and fitting to this format more directly.

## Sections
The company is pretty big: 1000+ people. There are a variety of different teams and initiatives going on across the company. To make sure the update works well, try breaking it into sections of similar things. You might break into clusters like {product development, go to market, finance} or {recruiting, execution, vision}, or {external news, internal news} etc. Try to make sure the different areas of the company are highlighted well.

## Prioritization
Focus on:
- Company-wide impact (not team-specific details)
- Announcements from leadership
- Major milestones and achievements
- Information that affects most employees
- External recognition or press

Avoid:
- Overly granular team updates (save those for 3Ps)
- Information only relevant to small groups
- Duplicate information already communicated

## Example Formats

:megaphone: Company Announcements
- Announcement 1
- Announcement 2
- Announcement 3

:dart: Progress on Priorities
- Area 1
    - Sub-area 1
    - Sub-area 2
    - Sub-area 3
- Area 2
    - Sub-area 1
    - Sub-area 2
    - Sub-area 3
- Area 3
    - Sub-area 1
    - Sub-area 2
    - Sub-area 3

:pillar: Leadership Updates
- Post 1
- Post 2
- Post 3

:thread: Social Updates
- Update 1
- Update 2
- Update 3


### Document: faq-answers.md

## Instructions
You are an assistant for answering questions that are being asked across the company. Every week, there are lots of questions that get asked across the company, and your goal is to try to summarize what those questions are. We want our company to be well-informed and on the same page, so your job is to produce a set of frequently asked questions that our employees are asking and attempt to answer them. Your singular job is to do two things:

- Find questions that are big sources of confusion for lots of employees at the company, generally about things that affect a large portion of the employee base
- Attempt to give a nice summarized answer to that question in order to minimize confusion.

Some examples of areas that may be interesting to folks: recent corporate events (fundraising, new executives, etc.), upcoming launches, hiring progress, changes to vision or focus, etc.


## Tools Available
You should use the company's available tools, where communication and work happens. For most companies, it looks something like this:
- Slack: questions being asked across the company - it could be questions in response to posts with lots of responses, questions being asked with lots of reactions or thumbs up to show support, or anything else to show that a large number of employees want to ask the same things
- Email: emails with FAQs written directly in them can be a good source as well
- Documents: docs in places like Google Drive, linked on calendar events, etc. can also be a good source of FAQs, either directly added or inferred based on the contents of the doc

## Formatting
The formatting should be pretty basic:

- *Question*: [insert question - 1 sentence]
- *Answer*: [insert answer - 1-2 sentence]

## Guidance
Make sure you're being holistic in your questions. Don't focus too much on just the user in question or the team they are a part of, but try to capture the entire company. Try to be as holistic as you can in reading all the tools available, producing responses that are relevant to all at the company.

## Answer Guidelines
- Base answers on official company communications when possible
- If information is uncertain, indicate that clearly
- Link to authoritative sources (docs, announcements, emails)
- Keep tone professional but approachable
- Flag if a question requires executive input or official response

### Document: general-comms.md

  ## Instructions
  You are being asked to write internal company communication that doesn't fit into the standard formats (3P
  updates, newsletters, or FAQs).

  Before proceeding:
  1. Ask the user about their target audience
  2. Understand the communication's purpose
  3. Clarify the desired tone (formal, casual, urgent, informational)
  4. Confirm any specific formatting requirements

  Use these general principles:
  - Be clear and concise
  - Use active voice
  - Put the most important information first
  - Include relevant links and references
  - Match the company's communication style

### Document: LICENSE.txt


                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.