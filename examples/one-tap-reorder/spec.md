# One-tap reorder (sample spec)

A grocery delivery app. Customers who order weekly rebuild almost the same basket every time.

**Idea.** Let a customer repeat their last order in a few taps: open "Reorder", check the items, pick a delivery slot, pay with the saved card.

**Where it shows up.** A banner on the home screen, a "Reorder" button on each past order, and a Sunday-evening push notification.

**Flow.**
1. Customer opens the reorder sheet. It lists the items of the last order with today's prices.
2. Items that are out of stock are flagged. The customer chooses a substitute or removes the item.
3. Customer picks a delivery slot.
4. Customer confirms payment with the saved card.
5. The order is placed and a confirmation is shown.

**Not decided yet.** What a customer with no past order sees. What happens if the saved card has expired. Whether the usual slot should be pre-selected.

**What we believe.**
- H1: at least 60% of customers who open the sheet place the order.
- H2: at least 25% of all active customers use it in the first month.
- H3: it takes under a minute.
- H4: at least 10% of new customers use it.
