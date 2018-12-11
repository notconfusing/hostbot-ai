To run on your local environment (Dev).
=======================================

You need a Wikitech tools-labs account and to access the Wikipedia database replicas from your local machine use:

```ssh -N maximilianklein@tools-dev.wmflabs.org -L 3306:enwiki.analytics.db.svc.eqiad.wmflabs:3306```

And copy the `replica.my.cnf` file you find in your tools-labs home folder to `config/replica.my.cnf`.


Note. storing things in the database requires: print candidate.user_name.decode('unicode_escape')
