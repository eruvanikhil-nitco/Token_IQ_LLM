# Building the images a customer installation runs

One image per installation, the all-in-one container built from the repository's `Dockerfile`.
The componentized gateway, backend, UI and migration images stay available for a customer who
outgrows a single container, but nothing deploys them today.

## The two rules

**Every image is tagged with the commit it was built from.** Never `latest`, never a branch
name. An installation whose version cannot be named cannot be rolled back to a known build,
and the manifest refuses such a version anyway, so producing one would only create an image
nobody is allowed to deploy.

**A dirty working tree stops the build.** The tag claims the image contains a particular
commit. Building from uncommitted changes makes that claim false, and it is discovered at the
worst possible moment: when a rollback puts code back that was never what was running.

There is an escape for a developer building a throwaway on their own machine. The release path
does not use it.

## What publishing to ECR will need

Nothing here has published anything, because there is no account. When there is, this is what
it takes.

One private ECR repository per image name, so `tokeniq/tokeniq` for the all-in-one. Repositories
should have tag immutability switched on, which makes the "never a moving tag" rule something
the registry enforces rather than something our tooling promises, and image scanning on push.

A lifecycle policy matters more here than it usually does. Every commit that ships produces an
image, they are large, and nothing deletes them on its own. Keep the versions any installation
currently runs plus a reasonable history to roll back into, and expire the rest.

Authentication is a short-lived token from the registry rather than a stored password, so
publishing from a developer machine and from CI work the same way.

The one thing to check on the first real push is the size and the pull time, because the pull
happens on every task start, and a slow one shows up as a slow deployment and a slow recovery
rather than as a slow build.

## What is proven and what is not

The tooling is tested: naming, tagging, refusing a moving tag, refusing a dirty tree, building
every image at one version, and stopping when a build fails.

The image itself is built locally from a clean checkout, which is the step that catches a
Dockerfile only working on the machine it was written on. Running that build is also what
found three broken dashboard calls, because the build type-checks the dashboard and no local
test run had.

Not proven: pushing to a registry, pulling from one, and anything about how the image behaves
under ECS. Those wait on an account.
