import { describe, expect, it } from "vitest";

import {
  CONNECT_CATEGORIES,
  connectableVendors,
  defaultMethodIndex,
  fieldProblem,
  missingRequiredFields,
  methodsFor,
  vendorNamed,
} from "./connectCatalogue";
import type { ConnectCategory } from "./connectCatalogue";

/**
 * The connect catalogue is the blueprint's own data rather than a design of mine, so what these
 * assert is the two ways reading it from a spec can still go wrong.
 *
 * A tile for a vendor nothing can connect is an empty promise: the customer picks it, fills a
 * form, and the save fails because no connector exists. And a method that claims to be the
 * recommended one when the recommended one is not built tells somebody their least-safe option is
 * the best available.
 */

describe("the five categories the blueprint specifies", () => {
  it("names all five, in the blueprint's order", () => {
    expect(CONNECT_CATEGORIES.map((category) => category.name)).toEqual([
      "AI provider",
      "AI tool",
      "Agent platform",
      "Cloud billing export",
      "Custom source",
    ]);
  });

  it("keeps a category with no connector as a category, with no tiles", () => {
    // The blueprint's structure is the answer to "where do I connect Copilot?", so dropping the
    // category leaves that question unanswered. What must not appear is a tile, because a tile
    // leads to a form that cannot save.
    const tools = CONNECT_CATEGORIES.find((category) => category.name === "AI tool");

    expect(tools).toBeDefined();
    expect(tools?.vendors).toEqual([]);
    expect(tools?.unavailable).toBeTruthy();
  });

  it("gives every category with no tiles a reason a reader can act on", () => {
    const empty = CONNECT_CATEGORIES.filter((category) => category.vendors.length === 0);

    expect(empty.length).toBeGreaterThan(0);
    for (const category of empty) {
      expect(category.unavailable).toBeTruthy();
    }
  });
});

describe("which vendors can actually be connected", () => {
  it("offers the providers whose bill this build can read", () => {
    expect(connectableVendors().map((vendor) => vendor.key)).toEqual([
      "aws",
      "azure",
      "claudeall",
      "openaiall",
      "openrouter",
      "vertex",
    ]);
  });

  it("offers no vendor without at least one method that works", () => {
    // The whole point of the available flag. A vendor whose only method is an unbuilt sign-in
    // would be a tile leading nowhere.
    for (const vendor of connectableVendors()) {
      expect(methodsFor(vendor.key).some((method) => method.available)).toBe(true);
    }
  });

  it("does not offer a seat or agent vendor as a provider account", () => {
    // Their spend arrives through the tool connectors and is on no provider bill. Connected here
    // it would be stored under a provider, which feeds tool spend into a provider figure.
    const keys = connectableVendors().map((vendor) => vendor.key);

    expect(keys).not.toContain("github");
    expect(keys).not.toContain("claude");
  });

  it("drops a vendor whose only method is not built", () => {
    // The guard the filter exists for. Every vendor in today's catalogue has a method that
    // works, so the rule is checked against one that does not rather than against the data.
    const signIn = methodsFor("azure").find((method) => !method.available)!;
    const onlyUnbuilt: ConnectCategory[] = [
      {
        name: "AI provider",
        summary: "a vendor behind a sign-in nobody built",
        vendors: [{ key: "someday", name: "Someday", summary: "x", methods: [signIn] }],
      },
    ];

    expect(connectableVendors(onlyUnbuilt)).toEqual([]);
  });

  it("finds a vendor by key", () => {
    expect(vendorNamed("aws")?.name).toBe("AWS Bedrock");
  });

  it("finds nothing for a key nobody offers", () => {
    expect(vendorNamed("not-a-vendor")).toBeUndefined();
  });
});

describe("the methods for one vendor", () => {
  it("gives AWS a role first and keys second, as the blueprint does", () => {
    const methods = methodsFor("aws");

    expect(methods.map((method) => method.kind)).toEqual(["role", "key"]);
    expect(methods[0].recommended).toBe(true);
  });

  it("starts on the recommended method that is actually available", () => {
    expect(defaultMethodIndex("aws")).toBe(0);
  });

  it("starts on a working method when the recommended one is not built", () => {
    // Azure's recommended method in the blueprint is Sign in with Microsoft, which this build
    // does not have. Opening on it would leave the dialog showing a form nobody can submit.
    const methods = methodsFor("azure");
    const chosen = methods[defaultMethodIndex("azure")];

    expect(chosen.available).toBe(true);
  });

  it("says why an unbuilt method is unavailable rather than hiding it", () => {
    // Hidden, the dialog silently recommends the least safe option. Named, the reader learns
    // their provider's better method exists and this build has not got to it.
    const unavailable = methodsFor("azure").filter((method) => !method.available);

    expect(unavailable.length).toBeGreaterThan(0);
    for (const method of unavailable) {
      expect(method.unavailableReason).toBeTruthy();
    }
  });

  it("gives a vendor nobody offers no methods at all", () => {
    expect(methodsFor("not-a-vendor")).toEqual([]);
  });

  it("asks the role method for a role ARN and never for an external ID", () => {
    // The external ID is minted and stored by the server. A field for it would let somebody
    // present a value they chose, which is what it exists to prevent.
    const names = methodsFor("aws")[0].fields.map((field) => field.name);

    expect(names).toContain("role_arn");
    expect(names).not.toContain("external_id");
  });

  it("never asks any method for an external ID", () => {
    for (const category of CONNECT_CATEGORIES) {
      for (const vendor of category.vendors) {
        for (const method of methodsFor(vendor.key)) {
          expect(method.fields.map((field) => field.name)).not.toContain("external_id");
        }
      }
    }
  });

  it("explains every field it asks for", () => {
    // The Setup guide tab is the blueprint's first tab and it explains each field. A field with
    // no explanation makes that tab lie about what it covers.
    for (const category of CONNECT_CATEGORIES) {
      for (const vendor of category.vendors) {
        for (const method of methodsFor(vendor.key)) {
          for (const field of method.fields) {
            expect(field.explanation, `${vendor.key} ${method.id} ${field.name}`).toBeTruthy();
          }
        }
      }
    }
  });
});

describe("what still has to be filled in", () => {
  const roleMethod = methodsFor("aws")[0];

  it("names a required field nobody has filled", () => {
    expect(missingRequiredFields(roleMethod, {})).toEqual(["Role ARN"]);
  });

  it("is satisfied once the required fields carry something", () => {
    expect(missingRequiredFields(roleMethod, { role_arn: "arn:aws:iam::1:role/x" })).toEqual([]);
  });

  it("treats whitespace as nothing", () => {
    // A pasted key that is only a newline reads as filled in and then fails the live test with
    // a message about the provider rather than about the form.
    expect(missingRequiredFields(roleMethod, { role_arn: "   " })).toEqual(["Role ARN"]);
  });

  it("ignores an optional field left empty", () => {
    const keysMethod = methodsFor("aws")[1];
    const filled = Object.fromEntries(
      keysMethod.fields.filter((field) => field.required).map((field) => [field.name, "x"]),
    );

    expect(missingRequiredFields(keysMethod, filled)).toEqual([]);
  });
});

describe("a field the provider will reject", () => {
  it("catches an ordinary key where an admin key is needed, before the live test", () => {
    // The provider answers an ordinary key with a 401 that says nothing about admin keys. The
    // prefix is knowable here, so saying it here is the difference between a fixable message and
    // a dead end.
    const adminKey = methodsFor("claudeall")[0].fields.find((field) => field.name === "api_key");

    expect(adminKey).toBeDefined();
    expect(fieldProblem(adminKey!, "sk-ant-api03-ordinary")).toContain("admin key");
  });

  it("accepts the admin key it asked for", () => {
    const adminKey = methodsFor("claudeall")[0].fields.find((field) => field.name === "api_key")!;

    expect(fieldProblem(adminKey, "sk-ant-admin01-real")).toBeNull();
  });

  it("says nothing about a field nobody has filled yet", () => {
    // Required-ness is reported separately. Both at once marks every empty form red on open.
    const adminKey = methodsFor("claudeall")[0].fields.find((field) => field.name === "api_key")!;

    expect(fieldProblem(adminKey, "")).toBeNull();
  });

  it("says nothing about a field with no known shape", () => {
    const roleArn = methodsFor("aws")[0].fields.find((field) => field.name === "role_arn")!;

    expect(fieldProblem(roleArn, "arn:aws:iam::123456789012:role/token-iq-read-only")).toBeNull();
  });

  it("catches a role ARN that is not one", () => {
    // Pasted from the wrong stack output, this is the commonest way the role method fails, and
    // AWS answers it with a validation error that names nothing a customer can act on.
    const roleArn = methodsFor("aws")[0].fields.find((field) => field.name === "role_arn")!;

    expect(fieldProblem(roleArn, "token-iq-read-only")).toBeTruthy();
  });
});
