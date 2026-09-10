import React, { useState } from "react";
import { CopyToClipboard } from "react-copy-to-clipboard";
import { Button } from "@/components/ui/button";
import { getProxyBaseUrl } from "@/components/networking";
import { toast } from "@/lib/toast";

interface CreatedKeyDisplayProps {
  apiKey: string;
  baseUrl?: string;
}

interface CopyableFieldProps {
  label: string;
  value: string;
  copyLabel: string;
  toastMessage: string;
}

/** A labelled read-only value with its own copy button and transient "Copied!" state. */
const CopyableField: React.FC<CopyableFieldProps> = ({ label, value, copyLabel, toastMessage }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    setCopied(true);
    toast.success(toastMessage);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mb-4">
      <p className="text-sm text-muted-foreground mb-1">{label}</p>
      <div className="bg-muted rounded-md p-2.5 mb-2">
        <pre className="m-0 whitespace-normal break-words text-foreground">{value}</pre>
      </div>
      <CopyToClipboard text={value} onCopy={handleCopy}>
        <Button variant="outline" size="sm">
          {copied ? "Copied!" : copyLabel}
        </Button>
      </CopyToClipboard>
    </div>
  );
};

/**
 * Shared component for displaying a newly-created virtual key.
 * Used on the Virtual Keys page and in the Add Agent wizard.
 *
 * Shows the base URL alongside the key: the key authenticates the caller but carries no
 * routing information, so an app given only the key reaches the provider directly instead
 * of this gateway.
 */
const CreatedKeyDisplay: React.FC<CreatedKeyDisplayProps> = ({ apiKey, baseUrl = getProxyBaseUrl() }) => {
  const [snippetCopied, setSnippetCopied] = useState(false);

  const snippet = `curl ${baseUrl}/v1/chat/completions \
  -H "Authorization: Bearer ${apiKey}" \
  -H "Content-Type: application/json" \
  -d '{"model": "your-model", "messages": [{"role": "user", "content": "hello"}]}'`;

  const handleSnippetCopy = () => {
    setSnippetCopied(true);
    toast.success("Example copied to clipboard");
    setTimeout(() => setSnippetCopied(false), 2000);
  };

  return (
    <div>
      <p className="mb-4">
        Please save this secret key somewhere safe and accessible. For security reasons,{" "}
        <b>you will not be able to view it again</b> through your Token IQ account. If you lose this secret key, you will
        need to generate a new one.
      </p>

      <CopyableField
        label="Virtual Key:"
        value={apiKey}
        copyLabel="Copy Virtual Key"
        toastMessage="Key copied to clipboard"
      />

      {baseUrl ? (
        <>
          <CopyableField
            label="Base URL:"
            value={baseUrl}
            copyLabel="Copy Base URL"
            toastMessage="Base URL copied to clipboard"
          />

          <p className="text-sm text-muted-foreground mb-1">Example request:</p>
          <div className="bg-muted rounded-md p-2.5 mb-2 overflow-x-auto">
            <pre className="m-0 text-xs text-foreground">{snippet}</pre>
          </div>
          <CopyToClipboard text={snippet} onCopy={handleSnippetCopy}>
            <Button variant="outline" size="sm">
              {snippetCopied ? "Copied!" : "Copy Example"}
            </Button>
          </CopyToClipboard>
        </>
      ) : null}
    </div>
  );
};

export default CreatedKeyDisplay;
