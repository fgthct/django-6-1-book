# Backup and Restore

## What is backed up

Customer databases, shared documents and server configurations are backed up. Personal files on laptops are not: save your work in the shared drive.

## Schedule

The nightly backup starts at 02:30 and normally ends before 04:00. A full copy is made every Sunday; on the other days only the changes are saved. Backups are kept for 35 days.

## Objectives

The recovery point objective (RPO) is 24 hours: in the worst case we lose one day of data. The recovery time objective (RTO) is four hours for customer databases and one working day for everything else.

## Restore tests

Every quarter the infrastructure team restores a random backup on a test server and checks that the data is complete. The result is recorded in the registry of restore tests, signed by the team lead.
