# Cost rules for the $100 Brev budget

1. Pick the cheapest instance with a 24 GB GPU (L4, A10G, or similar). Nimble
   needs ~18 GB for weights in bf16. Do NOT pick an A100/H100; it is not faster
   for this workload in any way you will notice, and it costs 3-4x.
2. Check the hourly price on the launch screen and write it down.
3. Start the instance only when someone is at the keyboard for the whole
   session. Stop it (not just close the tab) as soon as the run finishes.
   `scripts/run/run_nimble.py` prints "DONE - stop the instance now" when it exits.
4. Set a phone timer for 60 minutes every time you start it.
5. Delete the instance when you're done, don't just stop it. A stopped instance
   still bills for its disk (about $20/month for ours), and a fresh setup only
   takes ~10 minutes, which is cheaper than storing the models.
6. Never leave a Jupyter/notebook server running after a session.
7. Budget expectation: setup ~$1, each pilot run <$0.10, the full study <$5.
   The only way to overspend is an idle instance.
