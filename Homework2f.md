# Homework 2f

## How you completed the required tasks

- I chose to build an app that I'm very interested in, a **USCIS Form Helper**. It will keep a user's recurring immigration documents 
(passport, I-94, green card, prior receipt notices, address and employment history) in one local vault, or it might be a checklist,
so they can be reused across forms. It will also answer form-specific questions, for example: "Which address goes in Part 2 of the I-765?",
by retrieving the answer from official USCIS form instructions and the Policy Manual, with citations. I'm interested
in it because USCIS paperwork is repetitive, and the guidance is scattered across long PDFs, which makes 
the process stressful for applicants and make them more prone to make errors that cost them a lot of money.

## What additional exploration you did

- I considered these alternatives:
  - **Tool calling:** an agent that fills out the fillable USCIS PDFs itself by calling tools. I'll keep it as a supporting feature, because the 
  hardest part for applicants is understanding the instructions, not typing.
  - **Structured output:** focusing only on extracting data from scanned documents into 
  a typed profile. This would help applicants have a better interactions with the forms.

## What obstacles you encountered

- The main challenges I expect is that USCIS instructions are long PDFs
that change by edition date, so I need a reliable ingestion/chunking pipeline. Also, my agent must 
not give legal advice, always cite the source, and say "I don't know" when retrieval
is weak. Personal documents are sensitive, so I am debating between having the vault to stay local and private or
only having a checklist.

## What you learned

- Picking a core concept made me separate what needs an LLM from what doesn't. So far I think my core 
concept will be **Embeddings** by using RAG over official USCIS instructions, supported by structured 
output, which will extracting document fields into a typed profile, tool calling, LLM-as-judge, by checking that each answer 
is supported by the retrieved passages, and guardrails which will prevent any legal advice.

## Why this matters in the context of agent engineering

- I think it is important to an agent must cite reliable sources, and handle sensitive data 
safely. This will be a good way to understand when an agent can make the decision of something super important. Also,
that makes it a good test of hallucination guardrails, and of deciding where an LLM beats deterministic code versus 
where deterministic code is better.

## How many hours you spent on the homework

- 3.0 hours
