# What the customer said (auto parts workshop)

We run a small auto parts warehouse for our repair shop.

People: warehouse staff receive and ship parts. Buyers request
parts for repair jobs.

Parts: each part has a code (like W-002), a description, how many we
have in stock, and a minimum we want to keep (1 unless we say
otherwise). A part is active, or discontinued once we stop carrying
it; a discontinued part never comes back. Warehouse staff add and
change parts; everyone can look at them.

Requests: a buyer makes a fulfillment request for a repair job. It
has a job reference (like JOB-101), one part, and a quantity. It
starts as a draft. Buyers create requests; buyers and warehouse
staff can see and change them.

1. Request parts for a job. A buyer submits a draft request so the
   warehouse knows what to prepare. After that it is pending.
   Refuse it if the quantity is zero or less ("quantity must be
   positive"), if the part is discontinued ("part is discontinued"),
   or if it was already submitted ("fulfillment is already
   submitted").

2. Ship a request. Warehouse staff ship a pending request: it
   becomes shipped and the quantity comes off the part's stock.
   Refuse it if the request is not pending ("fulfillment is not
   pending") or if there is not enough stock ("insufficient
   stock").

3. Cancel a request. A buyer cancels a request they no longer need,
   whether it is a draft or pending; it becomes cancelled. A shipped
   or already cancelled request cannot be cancelled ("fulfillment
   cannot be cancelled").

Give each story a few examples, including each refusal. Group the
stories under one epic, FUL ("manage the auto parts inventory and
fulfil requests").
