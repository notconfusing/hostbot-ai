#!/usr/bin/env bash
ssh -N maximilianklein@tools-dev.wmflabs.org -L 3306:enwiki.analytics.db.svc.eqiad.wmflabs:3306
