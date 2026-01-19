===================
Merging new commits
===================

As part of our new focus on reliability, we want to make sure
that the spshw software is getting tested on hardware as often
as possible.

As a result we have made the decision to force every merge
request to be tested at RAL on the hardware deployment there.

In the pipeline there is now a manual stage called ral-low-k8s-test
Before you are allowed to merge, that stage MUST pass, you can
trigger it manually from gitlab.

Because other people may be using the deployment at RAL for
their own testing, it is important to make sure you're not running
the stage when other people are using it.

Check the calander here
https://confluence.skatelescope.org/display/LP/calendar/296dd980-02eb-4eb4-afa0-d1a09334d9c2?calendarName=RAL%20TPM%20Use#
To ensure you're not standing on anyones toes. Even better, book a
slot for yourself to run the test.

Because two people running tests at the same time can create some
nasty situations, the gitlab-ci stage has a series of checks
to validate its safe to run.

It checks that there are no other deployments currently at RAL
And it checks the calander to make sure no one else it using it.

HOWEVER, it is difficult to differentiate between users, so it
will reject the test even if you have booked the appointment.

To get around this you can add the keyword `PIPELINE_TEST` to the
description in the calander. This will allow the tests to run


Additionally, the ral-test stage now is part of the resource group 'ral-hardware'
in the gitlab-ci pipeline. This resource can be claimed by a single stage,
providing safety against concurrent hardware access.
What this means in practice is that gitlab will prevent you from running
the tests when another test is running.
If you do attempt to run the tests while others are running, the resource group
will add it to a queue and the new test set will be run once the old one has
finished.