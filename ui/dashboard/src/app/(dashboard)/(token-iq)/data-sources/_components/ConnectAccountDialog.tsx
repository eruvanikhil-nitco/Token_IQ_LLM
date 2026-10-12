"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import {
  bedrockPrincipalCall,
  bedrockRoleTemplateCall,
  connectAccountCall,
  connectionExternalIdCall,
  type BedrockPrincipal,
  type ConnectAccountResponse,
} from "@/components/networking";
import { unwrapProxyErrorMessage } from "@/lib/http/client";

import {
  CONNECT_CATEGORIES,
  defaultMethodIndex,
  fieldProblem,
  methodsFor,
  vendorNamed,
  type ConnectMethod,
  type ConnectVendor,
} from "./connectCatalogue";
import { canSubmit, connectPayload, needsExternalId, principalMessage, resultMessage } from "./connectSubmit";

/**
 * Data Sources: + Connect account.
 *
 * The blueprint's own dialog: five categories, four method kinds, and the two tabs it gives every
 * setup button, Setup guide then Configure. The shaping lives in `connectCatalogue.ts` and
 * `connectSubmit.ts`, both unit tested; what is here is the arrangement and the two calls.
 *
 * Nothing is saved until the connection test passes. That is enforced on the server, where one
 * endpoint tests the credential being offered and stores it only if the test came back fetched, so
 * it holds for any client rather than only for this one.
 */

type Screen = { at: "catalogue" } | { at: "vendor"; vendorKey: string };

function Guide({ method }: { method: ConnectMethod }) {
  return (
    <div className="flex flex-col gap-4">
      {method.steps ? (
        <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm">
          {method.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      ) : null}

      {method.fields.length > 0 ? (
        <div className="flex flex-col gap-3">
          <p className="text-xs font-medium text-muted-foreground">Each field explained</p>
          {method.fields.map((field) => (
            <div key={field.name} className="flex flex-col gap-1 rounded-md border p-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{field.label}</span>
                <Badge variant={field.required ? "default" : "secondary"}>
                  {field.required ? "Required" : "Optional"}
                </Badge>
              </div>
              <span className="text-sm text-muted-foreground">{field.explanation}</span>
              {field.example ? <span className="text-xs text-muted-foreground">Example: {field.example}</span> : null}
            </div>
          ))}
        </div>
      ) : null}

      {method.help.length > 0 ? (
        <div className="flex flex-col gap-1 rounded-md border p-3">
          <span className="text-sm font-medium">Where to find it</span>
          <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm text-muted-foreground">
            {method.help.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ol>
        </div>
      ) : null}

      <p className="text-xs text-muted-foreground">{method.reassurance}</p>
      <p className="text-xs text-muted-foreground">
        After you save: Token IQ tests the connection against the provider. Nothing is saved unless that test passes
      </p>
    </div>
  );
}

interface ExternalIdStepProps {
  externalId: string | null;
  note: string | null;
  busy: boolean;
  canIssue: boolean;
  onIssue: () => Promise<void>;
  onDownloadTemplate: () => Promise<void>;
}

/**
 * The role method's external ID, shown rather than asked for.
 *
 * Its own component because it is the one part of the form the customer does not fill in: the
 * value is minted and stored by the server, because a value the customer chose could be reused
 * across connections or copied out of somebody else's documentation, which is the whole thing an
 * external ID exists to prevent.
 */
function ExternalIdStep({ externalId, note, busy, canIssue, onIssue, onDownloadTemplate }: ExternalIdStepProps) {
  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <span className="text-sm font-medium">External ID</span>
      <span className="text-xs text-muted-foreground">
        Generated for you and stored, because your role trusts this exact value. It is never asked for and never typed
        in
      </span>
      {externalId ? (
        <div className="flex items-center gap-2">
          <code className="rounded bg-muted px-2 py-1 text-sm">{externalId}</code>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void navigator.clipboard?.writeText(externalId);
            }}
          >
            Copy
          </Button>
        </div>
      ) : (
        <Button
          variant="outline"
          size="sm"
          disabled={busy || !canIssue}
          onClick={() => {
            void onIssue();
          }}
          className="self-start"
        >
          Get the external ID for this account
        </Button>
      )}
      {note ? <span className="text-xs text-muted-foreground">{note}</span> : null}
      <Button
        variant="outline"
        size="sm"
        disabled={busy}
        onClick={() => {
          void onDownloadTemplate();
        }}
        className="self-start"
      >
        Download the CloudFormation template
      </Button>
    </div>
  );
}

/**
 * The template's other parameter, read from AWS rather than asked for.
 *
 * Nothing in the product recorded which principal this installation runs as, so this step used to
 * be a sentence telling the customer to go and ask whoever deployed Token IQ, at the one moment
 * they needed the value. `sts:GetCallerIdentity` needs no permission, so AWS can be asked directly.
 *
 * Its own component, which fetches only while the role method is showing: no other method needs
 * the value, and the call reaches out to AWS.
 */
function PrincipalStep() {
  const { accessToken } = useAuthorized();
  const [principal, setPrincipal] = useState<BedrockPrincipal | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    let current = true;
    bedrockPrincipalCall(accessToken)
      .then((answer) => {
        if (current) {
          setPrincipal(answer);
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setFailure(unwrapProxyErrorMessage(error instanceof Error ? error.message : String(error)));
        }
      });
    return () => {
      current = false;
    };
  }, [accessToken]);

  const message = principal === null ? null : principalMessage(principal);

  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <span className="text-sm font-medium">Token IQ principal</span>
      {message?.arn ? (
        <div className="flex items-center gap-2">
          <code className="rounded bg-muted px-2 py-1 text-sm break-all">{message.arn}</code>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void navigator.clipboard?.writeText(message.arn ?? "");
            }}
          >
            Copy
          </Button>
        </div>
      ) : null}
      {message ? (
        <span className={`text-xs ${message.tone === "unknown" ? "text-destructive" : "text-muted-foreground"}`}>
          {message.text}
        </span>
      ) : null}
      {failure ? <span className="text-xs text-destructive">{failure}</span> : null}
      {message === null && failure === null ? (
        <span className="text-xs text-muted-foreground">Asking AWS which principal this installation runs as...</span>
      ) : null}
    </div>
  );
}

/** * What are you connecting? The blueprint's five categories, with tiles only where a connector
 * exists and a reason where one does not.
 */
function Catalogue({ onPick }: { onPick: (vendor: ConnectVendor) => void }) {
  return (
    <div className="flex flex-col gap-5">
      <p className="text-xs font-medium text-muted-foreground">What are you connecting?</p>
      {CONNECT_CATEGORIES.map((category) => (
        <div key={category.name} className="flex flex-col gap-2">
          <span className="text-sm font-medium">{category.name}</span>
          <span className="text-xs text-muted-foreground">{category.summary}</span>
          {category.vendors.length === 0 ? (
            <p className="text-xs text-muted-foreground">{category.unavailable}</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {category.vendors.map((entry) => (
                <button
                  key={entry.key}
                  type="button"
                  onClick={() => onPick(entry)}
                  className="flex flex-col items-start gap-1 rounded-md border p-3 text-left hover:bg-accent"
                >
                  <span className="text-sm font-medium">{entry.name}</span>
                  <span className="text-xs text-muted-foreground">{entry.summary}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function ConnectAccountDialog() {
  const { accessToken } = useAuthorized();
  const [open, setOpen] = useState(false);
  const [screen, setScreen] = useState<Screen>({ at: "catalogue" });
  const [methodIndex, setMethodIndex] = useState(0);
  const [tab, setTab] = useState<0 | 1>(0);
  const [accountName, setAccountName] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [externalId, setExternalId] = useState<string | null>(null);
  const [externalIdNote, setExternalIdNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ConnectAccountResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const reset = () => {
    setScreen({ at: "catalogue" });
    setMethodIndex(0);
    setTab(0);
    setAccountName("");
    setValues({});
    setExternalId(null);
    setExternalIdNote(null);
    setResult(null);
    setFailure(null);
  };

  const pick = (vendor: ConnectVendor) => {
    setScreen({ at: "vendor", vendorKey: vendor.key });
    setMethodIndex(defaultMethodIndex(vendor.key));
    setTab(0);
    setValues({});
    setExternalId(null);
    setExternalIdNote(null);
    setResult(null);
    setFailure(null);
  };

  const vendor = screen.at === "vendor" ? vendorNamed(screen.vendorKey) : undefined;
  const methods = vendor ? methodsFor(vendor.key) : [];
  const method = methods[methodIndex];

  const issueExternalId = async () => {
    if (!accessToken || !vendor) {
      return;
    }
    setBusy(true);
    setFailure(null);
    try {
      const issued = await connectionExternalIdCall(accessToken, vendor.key, accountName.trim());
      setExternalId(issued.external_id);
      setExternalIdNote(
        issued.kind === "already_issued"
          ? "This account already had an external ID, so the role you created with it still works. Nothing to redo in AWS"
          : null,
      );
    } catch (error) {
      setFailure(unwrapProxyErrorMessage(error instanceof Error ? error.message : String(error)));
    } finally {
      setBusy(false);
    }
  };

  const downloadTemplate = async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setFailure(null);
    try {
      const fetched = await bedrockRoleTemplateCall(accessToken);
      const url = URL.createObjectURL(new Blob([fetched.template], { type: "text/yaml" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = fetched.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setFailure(unwrapProxyErrorMessage(error instanceof Error ? error.message : String(error)));
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!accessToken || !vendor || !method) {
      return;
    }
    setBusy(true);
    setFailure(null);
    setResult(null);
    const draft = { vendorKey: vendor.key, accountName, method, values };
    try {
      setResult(await connectAccountCall(accessToken, connectPayload(draft)));
    } catch (error) {
      setFailure(unwrapProxyErrorMessage(error instanceof Error ? error.message : String(error)));
    } finally {
      setBusy(false);
    }
  };

  const readiness = method === undefined ? null : { accountName, method, values, externalId };
  const ready = readiness === null ? false : canSubmit(readiness);
  const message = result ? resultMessage(result) : null;
  // The external ID is tied to this account name, because the role in the customer's account
  // trusts that exact value. Renaming after one has been issued would test a different connection
  // and leave the role they already created pointing at nothing.
  const nameLocked = externalId !== null;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          reset();
        }
      }}
    >
      <DialogTrigger render={<Button />}>+ Connect account</DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Connect account</DialogTitle>
          <DialogDescription>
            Connect a source of AI usage or cost. Every connection is read-only: Token IQ can never change the account
            or spend money
          </DialogDescription>
        </DialogHeader>

        {screen.at === "catalogue" || !vendor || !method ? (
          <Catalogue onPick={pick} />
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{vendor.name}</span>
              <Button variant="ghost" size="sm" onClick={reset}>
                Change
              </Button>
            </div>

            <div role="tablist" aria-label="Connection method" className="flex flex-wrap gap-2">
              {methods.map((entry, index) => (
                <button
                  key={entry.id}
                  type="button"
                  role="tab"
                  aria-selected={index === methodIndex}
                  onClick={() => {
                    setMethodIndex(index);
                    setResult(null);
                  }}
                  className={`rounded-md border px-3 py-1 text-sm ${index === methodIndex ? "bg-accent" : ""}`}
                >
                  {entry.label}
                  {/* An unavailable method says so on the strip itself. Labelled like any other
                      tab it reads as a working option, and a reader who never clicks it never
                      learns their provider offers something this build has not got. */}
                  {entry.available ? null : <span className="ml-2 text-xs text-muted-foreground">Not built yet</span>}
                  {entry.recommended && entry.available ? (
                    <span className="ml-2 text-xs text-muted-foreground">Recommended</span>
                  ) : null}
                </button>
              ))}
            </div>

            {method.available ? null : <p className="text-sm text-muted-foreground">{method.unavailableReason}</p>}

            <div role="tablist" aria-label="Setup" className="flex gap-2">
              {(["Setup guide", "Configure"] as const).map((label, index) => (
                <button
                  key={label}
                  type="button"
                  role="tab"
                  aria-selected={tab === index}
                  onClick={() => setTab(index === 0 ? 0 : 1)}
                  className={`rounded-md border px-3 py-1 text-sm ${tab === index ? "bg-accent" : ""}`}
                >
                  {index + 1}. {label}
                </button>
              ))}
            </div>

            {tab === 0 ? (
              <Guide method={method} />
            ) : (
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-1">
                  <Label htmlFor="connect-account-name">Account name</Label>
                  <Input
                    id="connect-account-name"
                    value={accountName}
                    disabled={nameLocked}
                    onChange={(event) => setAccountName(event.target.value)}
                    placeholder="aws-main"
                  />
                  <span className="text-xs text-muted-foreground">
                    {nameLocked
                      ? "Fixed now that an external ID has been issued for it, because the role in your account trusts that exact value"
                      : "How this account appears across Token IQ"}
                  </span>
                </div>

                {needsExternalId(method) ? <PrincipalStep /> : null}

                {needsExternalId(method) ? (
                  <ExternalIdStep
                    externalId={externalId}
                    note={externalIdNote}
                    busy={busy}
                    canIssue={accountName.trim() !== ""}
                    onIssue={issueExternalId}
                    onDownloadTemplate={downloadTemplate}
                  />
                ) : null}

                {method.fields.map((field) => {
                  const problem = fieldProblem(field, values[field.name] ?? "");
                  return (
                    <div key={field.name} className="flex flex-col gap-1">
                      <div className="flex items-center justify-between">
                        {/* The asterisk is decoration; `required` on the input is what a
                            screen reader reads, and it keeps the label's text the field's own
                            name rather than its name plus a symbol. */}
                        <span className="flex items-center gap-1">
                          <Label htmlFor={`connect-${field.name}`}>{field.label}</Label>
                          {field.required ? <span aria-hidden="true">*</span> : null}
                        </span>
                        {/* The blueprint's own link back to the explanation. Named for the
                            field it belongs to, because one page carries several and
                            "What is this?" alone names none of them. */}
                        <button
                          type="button"
                          aria-label={`What is ${field.label}?`}
                          onClick={() => setTab(0)}
                          className="text-xs text-primary underline-offset-4 hover:underline"
                        >
                          What is this?
                        </button>
                      </div>
                      <Input
                        id={`connect-${field.name}`}
                        type={field.type === "secret" ? "password" : "text"}
                        required={field.required}
                        autoComplete="off"
                        value={values[field.name] ?? ""}
                        placeholder={field.placeholder}
                        onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
                      />
                      {problem ? <span className="text-xs text-destructive">{problem}</span> : null}
                    </div>
                  );
                })}
              </div>
            )}

            {failure ? <p className="text-sm text-destructive">{failure}</p> : null}
            {message ? (
              <p className={`text-sm ${message.tone === "connected" ? "text-foreground" : "text-destructive"}`}>
                {message.text}
              </p>
            ) : null}

            <div className="flex justify-end gap-2">
              {tab === 0 ? (
                <Button onClick={() => setTab(1)} disabled={!method.available}>
                  Continue to configure
                </Button>
              ) : (
                <Button
                  onClick={() => {
                    void submit();
                  }}
                  disabled={!ready || busy}
                >
                  {busy ? "Testing..." : "Test and connect"}
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
