---
name: Work item (user story, fix, chore, docs)
about: Says what a test will check, before the work starts (AGENTS.md, "What an issue says")
title: "<spec> <kind><n>: "
---

## Problem

What is wrong or missing, in plain words, and who it matters to.

## Done when

- One line for each thing a test will check, written so that it is true or false.

## Contract

- Every name a test will use that is not in the repository yet: functions and their arguments, command-line
  options, files and paths, exact messages and values. Write "No new names" if there are none.
- For data: each table or file with its grain (one row per what), its columns with their typed suffixes, and its
  keys.

## Read first

- The spec's user story, the files to change and the docs that govern them, as links or paths.
