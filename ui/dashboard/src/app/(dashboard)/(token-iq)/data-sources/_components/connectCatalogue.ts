/**
 * The connect catalogue, from the blueprint's own data rather than from a design of mine.
 *
 * Five categories, four method kinds and each field's label, type, explanation, example and
 * required flag come from `TIQ_MODALS.connect` and the `METHODS` table beside it. Two decisions
 * depart from the mockup and both are about not promising what this build cannot do.
 *
 * A category with no connector keeps its place and shows no tiles. Dropped, the dialog has no
 * answer to "where do I connect Copilot?"; given a tile, it leads to a form whose save fails
 * because nothing can read that vendor's bill.
 *
 * A method the blueprint recommends but this build has not got, which is every sign-in, is listed
 * as unavailable with the reason rather than hidden. Hidden, the dialog silently recommends the
 * least safe option left; named, the reader learns their provider offers something better and this
 * build has not reached it.
 */

/** The four kinds the blueprint specifies. `kind` decides how the Configure tab renders. */
export type MethodKind = "role" | "guided" | "oauth" | "key";

export type FieldType = "text" | "secret";

export interface ConnectField {
  /** The credential value this becomes. Must be inside the provider's server-side allowlist. */
  name: string;
  label: string;
  type: FieldType;
  placeholder: string;
  /** What the Setup guide tab shows. Every field has one, because that tab claims to cover them. */
  explanation: string;
  example: string;
  required: boolean;
  /** A prefix the provider's own API requires, checked before the live test rather than after. */
  requiredPrefix?: string;
  /** A shape the value must match, with the message to show when it does not. */
  pattern?: RegExp;
  patternProblem?: string;
}

export interface ConnectMethod {
  id: string;
  label: string;
  kind: MethodKind;
  recommended: boolean;
  available: boolean;
  /** Why this build cannot offer it. Required whenever `available` is false. */
  unavailableReason?: string;
  fields: readonly ConnectField[];
  /** Where to find what the fields ask for, as the blueprint's "Where to find it" panel. */
  help: readonly string[];
  /** What is and is not stored, which is the blueprint's reassurance copy. */
  reassurance: string;
  /** The role method's numbered steps, which are its whole shape. */
  steps?: readonly string[];
}

export interface ConnectVendor {
  /** The catalogue's own key, which the connect endpoint translates to a provider. */
  key: string;
  name: string;
  summary: string;
  methods: readonly ConnectMethod[];
}

export interface ConnectCategory {
  name: string;
  summary: string;
  vendors: readonly ConnectVendor[];
  /** Why this category has no tiles. Set on every category whose vendors are empty. */
  unavailable?: string;
}

const NOTHING_SECRET =
  "Nothing secret is stored. Token IQ asks AWS for short-lived access each time it syncs, and your security team can see and delete the role whenever they like.";

const READ_ONLY =
  "Stored encrypted and never shown again. Token IQ only reads: it cannot create keys, change settings or spend money.";

const ACCOUNT_OWNER_SIGN_IN =
  "This build has no sign-in flow yet, so the account's own credentials are the way in. The sign-in the provider offers is the better method and is not built.";

const ROLE_ARN_PATTERN = /^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:role\/.+$/;

const AWS_ROLE: ConnectMethod = {
  id: "role",
  label: "IAM role",
  kind: "role",
  recommended: true,
  available: true,
  steps: [
    "Download the CloudFormation template and open CloudFormation in your own AWS account.",
    "Create the stack with the external ID below. It creates a read-only role trusted only by Token IQ, and nothing else.",
    "Copy the Role ARN from the stack outputs and paste it here.",
  ],
  fields: [
    {
      name: "role_arn",
      label: "Role ARN",
      type: "text",
      placeholder: "arn:aws:iam::123456789012:role/token-iq-read-only",
      explanation:
        "The role the stack created, from its Outputs tab. Token IQ assumes this role to read Cost Explorer and nothing else.",
      example: "arn:aws:iam::123456789012:role/token-iq-read-only",
      required: true,
      pattern: ROLE_ARN_PATTERN,
      patternProblem:
        "That is not a role ARN. Take the RoleArn value from the stack's Outputs tab, which starts arn:aws:iam: and contains :role/",
    },
  ],
  help: [
    "The template takes two parameters and both are shown here: the external ID, and the AWS principal this Token IQ installation runs as, which is read from AWS rather than typed.",
    "The role it creates grants one action, ce:GetCostAndUsage, which is the only call the connector makes.",
    "Deleting the stack ends Token IQ's access immediately.",
  ],
  reassurance: NOTHING_SECRET,
};

const AWS_KEYS: ConnectMethod = {
  id: "keys",
  label: "Access keys",
  kind: "key",
  recommended: false,
  available: true,
  fields: [
    {
      name: "aws_access_key_id",
      label: "Access key ID",
      type: "text",
      placeholder: "AKIA...",
      explanation: "A long-lived key in your account. Not recommended: use the IAM role unless a role is refused.",
      example: "AKIAIOSFODNN7EXAMPLE",
      required: true,
    },
    {
      name: "aws_secret_access_key",
      label: "Secret access key",
      type: "secret",
      placeholder: "",
      explanation: "The secret half of the key pair. Stored encrypted and never shown again.",
      example: "",
      required: true,
    },
    {
      name: "service_name",
      label: "Service name on your bill",
      type: "text",
      placeholder: "Amazon Bedrock",
      explanation:
        "What your bill calls the service. Configurable because a filter matching nothing returns an empty result rather than an error, which would otherwise show as a confident zero.",
      example: "Amazon Bedrock",
      required: false,
    },
  ],
  help: [
    "Only if your security team cannot allow a cross-account role.",
    "Use an IAM user with Cost Explorer read-only access.",
    "Rotate these keys every 90 days.",
  ],
  reassurance: READ_ONLY,
};

const adminKeyMethod = ({ prefix, where, reads }: { prefix: string; where: string; reads: string }): ConnectMethod => ({
  id: "guided",
  label: "Admin key",
  kind: "guided",
  recommended: true,
  available: true,
  steps: [
    `Sign in to ${where} as the organisation admin.`,
    'Create a read-only admin key named "Token IQ (read-only)", so your team can tell later what it is for.',
    "Paste it here.",
  ],
  fields: [
    {
      name: "api_key",
      label: "Admin key",
      type: "secret",
      placeholder: `${prefix}...`,
      explanation: `An organisation admin key, which is the only kind that can read ${reads}. An ordinary API key saves fine and then fails every sync with a 401.`,
      example: `${prefix}...`,
      required: true,
      requiredPrefix: prefix,
    },
  ],
  help: [
    `Create the key in ${where}`,
    "It must be an admin key, not an ordinary API key. Cost reports answer only to an admin key.",
    "You can delete the key at the provider at any time, and Token IQ stops reading at once.",
  ],
  reassurance: READ_ONLY,
});

const SIGN_IN_NOT_BUILT = (provider: string, button: string): ConnectMethod => ({
  id: "oauth",
  label: button,
  kind: "oauth",
  recommended: true,
  available: false,
  unavailableReason: `${provider} recommends this and Token IQ has no sign-in flow yet. ${ACCOUNT_OWNER_SIGN_IN}`,
  fields: [],
  help: [],
  reassurance: READ_ONLY,
});

const VENDORS: readonly ConnectVendor[] = [
  {
    key: "aws",
    name: "AWS Bedrock",
    summary: "Model spend on your AWS bill, read through Cost Explorer",
    methods: [AWS_ROLE, AWS_KEYS],
  },
  {
    key: "azure",
    name: "Microsoft Azure OpenAI",
    summary: "Azure Cost Management, by subscription",
    methods: [
      SIGN_IN_NOT_BUILT("Azure", "Sign in with Microsoft"),
      {
        id: "sp",
        label: "Subscription",
        kind: "key",
        recommended: false,
        available: true,
        fields: [
          {
            name: "subscription_id",
            label: "Subscription ID",
            type: "text",
            placeholder: "00000000-0000-0000-0000-000000000000",
            explanation:
              "The subscription whose Azure OpenAI cost Token IQ reads. One connection per subscription, so each one's cost stays its own.",
            example: "00000000-0000-0000-0000-000000000000",
            required: true,
          },
          {
            name: "service_name",
            label: "Service name on your bill",
            type: "text",
            placeholder: "Cognitive Services",
            explanation:
              "What your bill calls the service, for the same reason as on AWS: a filter matching nothing returns an empty result rather than an error.",
            example: "Cognitive Services",
            required: false,
          },
        ],
        help: [
          "Give the identity Token IQ runs as Cost Management Reader on the subscription.",
          "Only the subscription ID is stored here: the credentials come from the environment Token IQ runs in.",
        ],
        reassurance: READ_ONLY,
      },
    ],
  },
  {
    key: "claudeall",
    name: "Anthropic",
    summary: "Usage, cost and Claude Code reports from the Claude Console",
    methods: [
      adminKeyMethod({
        prefix: "sk-ant-admin",
        where: "platform.claude.com, Settings then Admin keys",
        reads: "usage, cost and Claude Code reports",
      }),
    ],
  },
  {
    key: "openaiall",
    name: "OpenAI",
    summary: "Usage and costs for every project in the organisation",
    methods: [
      adminKeyMethod({
        prefix: "sk-admin-",
        where: "platform.openai.com, Organization settings then Admin keys",
        reads: "usage and costs for every project",
      }),
    ],
  },
  {
    key: "openrouter",
    name: "OpenRouter",
    summary: "Per-request activity and cost",
    methods: [
      {
        id: "key",
        label: "API key",
        kind: "key",
        recommended: true,
        available: true,
        fields: [
          {
            name: "api_key",
            label: "API key",
            type: "secret",
            placeholder: "sk-or-...",
            explanation:
              "A key from your OpenRouter account. OpenRouter reports per request, so this is the one source with a figure for every call.",
            example: "sk-or-v1-...",
            required: true,
          },
        ],
        help: ["Create the key in openrouter.ai, under Keys.", "A read-only key is enough; Token IQ only reads."],
        reassurance: READ_ONLY,
      },
    ],
  },
  {
    key: "vertex",
    name: "Google Vertex AI",
    summary: "Cloud Billing export in BigQuery",
    methods: [
      SIGN_IN_NOT_BUILT("Google Cloud", "Sign in with Google"),
      {
        id: "sa",
        label: "Billing export",
        kind: "key",
        recommended: false,
        available: true,
        fields: [
          {
            name: "billing_project_id",
            label: "Billing project ID",
            type: "text",
            placeholder: "my-billing-project",
            explanation: "The project that holds the Cloud Billing export, which is where the cost figures are.",
            example: "my-billing-project",
            required: true,
          },
          {
            name: "billing_export_table",
            label: "Billing export table",
            type: "text",
            placeholder: "project.dataset.table",
            explanation:
              "The BigQuery table the export writes to, written project.dataset.table. A reference in any other shape is refused here rather than at the first sync.",
            example: "my-project.billing.gcp_billing_export_v1",
            required: true,
          },
        ],
        help: [
          "Enable the Cloud Billing export to BigQuery.",
          "Give the identity Token IQ runs as BigQuery Data Viewer on that dataset.",
          "Paste the project and table here.",
        ],
        reassurance: READ_ONLY,
      },
    ],
  },
];

export const CONNECT_CATEGORIES: readonly ConnectCategory[] = [
  {
    name: "AI provider",
    summary: "Anthropic, OpenAI, Azure OpenAI, AWS Bedrock, Google Vertex AI",
    vendors: VENDORS,
  },
  {
    name: "AI tool",
    summary: "Claude Code, Cursor, GitHub Copilot, ChatGPT and Claude workspaces",
    vendors: [],
    unavailable:
      "Tool usage already arrives through the tool connectors, which are configured outside this dialog. Their spend is on no provider bill, so connecting one here would file it under a provider.",
  },
  {
    name: "Agent platform",
    summary: "Kore.ai, CrewAI, Copilot Studio, Agentforce, LangSmith",
    vendors: [],
    unavailable: "No connector in this build. A tile here would lead to a form whose save cannot succeed.",
  },
  {
    name: "Cloud billing export",
    summary: "AWS, Azure or Google Cloud cost exports",
    vendors: [],
    unavailable:
      "Connect the provider instead: AWS Bedrock reads Cost Explorer and Vertex AI reads the BigQuery billing export, which is the same data for the AI services.",
  },
  {
    name: "Custom source",
    summary: "Any other company or system, connected any way",
    vendors: [],
    unavailable:
      "No connector in this build. Until there is one, upload the invoices so the months can still be reconciled.",
  },
];

/**
 * Every vendor this build can actually connect, in the order the catalogue lists them.
 *
 * Takes the categories so the rule can be exercised against a vendor whose only method is
 * unbuilt. Every vendor in today's catalogue has one that works, so without that the filter is a
 * guard nothing tests, and the first vendor added behind an unbuilt sign-in would get a tile
 * leading to a form nobody can submit.
 */
export function connectableVendors(
  categories: readonly ConnectCategory[] = CONNECT_CATEGORIES,
): readonly ConnectVendor[] {
  return categories
    .flatMap((category) => category.vendors)
    .filter((vendor) => vendor.methods.some((method) => method.available));
}

export function vendorNamed(key: string): ConnectVendor | undefined {
  return CONNECT_CATEGORIES.flatMap((category) => category.vendors).find((vendor) => vendor.key === key);
}

export function methodsFor(key: string): readonly ConnectMethod[] {
  return vendorNamed(key)?.methods ?? [];
}

/**
 * Which method the dialog opens on.
 *
 * The recommended one when it is available, and otherwise the first that is. Opening on an
 * unavailable method leaves the dialog showing a form nobody can submit, with no hint that
 * another tab works.
 */
export function defaultMethodIndex(key: string): number {
  const methods = methodsFor(key);
  const recommended = methods.findIndex((method) => method.recommended && method.available);
  return recommended === -1
    ? Math.max(
        methods.findIndex((method) => method.available),
        0,
      )
    : recommended;
}

/** Required fields with nothing in them, by label, for the message before the live test runs. */
export function missingRequiredFields(method: ConnectMethod, values: Readonly<Record<string, string>>): string[] {
  return method.fields
    .filter((field) => field.required && (values[field.name] ?? "").trim() === "")
    .map((field) => field.label);
}

/**
 * What is wrong with one value, where it is knowable without asking the provider.
 *
 * Only two things are: a key that is not an admin key, and an ARN that is not one. Both are
 * answered by the provider with a message naming nothing a customer can act on, so saying it here
 * is the difference between a fixable form and a dead end. An empty field says nothing, because
 * required-ness is reported separately and both at once marks every fresh form red.
 */
export function fieldProblem(field: ConnectField, value: string): string | null {
  const trimmed = value.trim();
  if (trimmed === "") {
    return null;
  }
  if (field.requiredPrefix && !trimmed.startsWith(field.requiredPrefix)) {
    return `This is an ordinary API key. Cost reports need an organisation admin key, which starts ${field.requiredPrefix}`;
  }
  if (field.pattern && !field.pattern.test(trimmed)) {
    return field.patternProblem ?? "That is not the shape this field expects";
  }
  return null;
}
