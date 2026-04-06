<context>
Scam and nuisance calls are a common challenge for landline owners, which are primarily elderly who are more susceptible to scam calls. While powerful tools exist for cell phone users, landline (including VOIP-based landlines) users do not have analogous capabilities.

Using Twilio or any alternative mechanisms, an AI LLM based voice processing system is needed to screen calls and make a decision whether the calls are legitimate or scam calls and process appropriately. To reduce the number of calls the AI model needs to process, mechanisms should be in place to block/ignore/disconnect known scam and nuisance numbers, and implement other screening mechanisms like recording call purpose or requiring some action (like press 1 to connect) for the call to either be forwarded to the recipient or to the LLM model for further screening.
</context>

<end user profile>
Elderly with little to no technical experience or acumen. It is expected that the end users will have access to email, laptop or tablet, smart television, and a desktop phone.
</end user profile>

<requirements>
1. Administrative portal for use by family and/or caretakers to configure and manage the system.
2. Supports number whitelisting
3. Automatic number identification and lookup, particularly for medical related companies
4. Full call intercept so it does not ring the recipient until post-screening
5. Message taking capabilities with email, sms, messaging app, or accompanying application or AI assistant recipient interface to relay the information to the recipient
6. Message forking - copy and forward messages to a caretaker based on assessed priority
7. Voice LLM answering and interaction support.
	1. Answer incoming calls with voice interaction support
	2. Provide an introduction/message explaining the use of an answering service, and security of the information shared
	3. Ask clarifying questions about who the caller is trying to reach, and what the purpose of the call is
	4. Recognize robo-calls for medical appointment confirmation, or forwarding to a human representative
	5. Supports keypad input when needed
8. Highly secure storing and access of sensitive information
9. Full bi-directional API for integration with other applications, services, and AI platforms
10. Does not interfere with outgoing 911 or emergency services calls
11. Does not interfere with incoming response calls from emergency services (police, fire department, ambulance, 911 callback)
</requirements>

<features>
1. Forward whitelisted or high-confidence numbers.
2. Identify inbound calls from medical services
3. Accept recorded messages and forward to recipient
4. Caller intent interview and assessment
5. Rate inbound calls based on confidence of legitimacy using all available public data services and best practices for call authentication
6. AI-enabled summarization and call details
7. Calendar integration to create, modify, remove calendar events based on incoming call details (like scheduling medical appointments)
8. Alternative call answering characters/personalities when answering known or low-confidence of legitimacy calls
	1. Character/voice selectable by end user
	2. Supports end-user provided scripts (AI enabled)
	3. Only applies to scam/nuisance calls
	4. Ties up scam caller lines by pretending to be a victim and provided plausible sounding, but fake, sensitive details.
	5. Interact with scam/nuisance callers in frustrating or highly confusing ways
9. Supports speech to text for hard of hearing end users
10. Supports audio messages and communication for blind or poor eyesight end users
</features>

<assumptions>
1. Landline numbers will be ported to a VOIP service or locally hosted PBX
2. Twilio or similar service subscription
3. AI model subscription will be available
</assumptions>

<design criteria>
Research current capabilities of similar commercial offerings and design a competitive solution for open-source, MIT license open use.

Use all available public registries of scam/nuisance numbers, methods, and mechanisms, but include capability to adapt to evolving methods, updated lists, and detection mechanisms.

Utilize all available phone technology to more accurately assess call intent and legitimacy.

Design the architecture through comprehensive review by multiple models. methods, and agents. Look for architectural flaws, missing design criteria, overly complex solutions where simpler solutions may be available, overlooked use cases and features. Assess based on highly critical point of view, malicious attacker/adversary point of view, and competitor assessment and criticism point of view. Create adversarial assessment and adjust the plan appropriately.

Include deep research on manipulation techniques, high pressure sales, urgency, and other cognitive bias based techniques implemented by scammers and unscrupulous sales. Assess and counter the risks posed by adversarial AI.

Use the learned manipulation (of both human and AI) techniques against scam/nuisance callers as appropriate, legal, and ethical when using the role-playing/character call answering/interaction service.

Review the plan, code, and implementation for security vulnerabilities. Complete security assessments, code review, and pentesting as a central control mechanism in the design and implementation of the solution.
</design criteria>

<interface>
1. Web admin portal
2. Web end user portal
3. Voice interaction
4. SMS interaction
5. Message service interaction (telegram, whatsapp, discord, facebook messenger, etc.)
6. API
7. MCP
</interface>

<process>
Assess features, intent, and requirements. Ask clarifying questions as necessary. Create full documentation on requirements, dependencies, supply chain, use cases, and architecture. Generate an implementation plan in phases/sprints, identifying dependencies, parallel operations (for multi-agent coordination), roadmap, development/coding standards, and security requirements/standards. Build the plan and manage progress so it can be picked up and continued at any time by any AI platform. Use Github to manage code, plan phases/sprints, create tasks and issues, coordinate work. Use shared memory files where appropriate to improve multi-agent coordination and grounding.

Phases can contain multiple sprints. Each sprint should have a set of objectives which can be built, integrated, deployed, tested, and assessed before moving to the next sprint. A sprint can include multiple objectives completed by multiple coding agents, integrated by an integration test agent, reviewed by a security expert agent, and managed by a project manager.

1. Create requirements, features, use cases
2. Design architecture
3. Build development/implementation plan
4. Complete critical feature assessment, best practices, gap analysis
5. Complete comprehensive security review
6. Adjust architecture and plan as necessary
7. Repeat review and architecture/plan adjustments until no critical, major, or high issues are identified
8. Begin development of each phase/sprint process
	1. Complete coding
	2. Security code review
	3. Code update based on findings
	4. Code integration
	5. Deployment and smoke testing
	6. Platform security assessment
	7. Pentesting
	8. Release approval review
	9. Release
9. When all Phases/sprints are complete, do a final code review, code security review, integration, build testing, deployment, smoke testing, feature review, security audit, and pentesting pass.
10. Create backlog for future features, non-critical issue resolution, and non-critical security mitigations.
11. Product release
</process>
