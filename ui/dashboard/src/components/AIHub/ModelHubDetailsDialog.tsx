"use client";

import { Badge } from "@/components/ui/badge";
import { getProxyBaseUrl } from "@/components/networking";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { prism } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useSyntaxTheme } from "@/hooks/useSyntaxTheme";
import {
  formatCapabilityName,
  formatCost,
  getModelCapabilities,
  type ModelHubData,
} from "@/components/AIHub/ModelHubTableColumns";

interface ModelHubDetailsDialogProps {
  /** The model to describe, or null when the dialog is closed. */
  selectedModel: ModelHubData | null;
  onClose: () => void;
}

/**
 * The AI Hub model-details dialog, extracted so the Providers page shows the same
 * detail view rather than a second implementation that drifts from it.
 */
const ModelHubDetailsDialog: React.FC<ModelHubDetailsDialogProps> = ({ selectedModel, onClose }) => {
  const syntaxTheme = useSyntaxTheme(prism);

  return (
    <Dialog open={selectedModel !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-[1000px]">
        <DialogHeader>
          <DialogTitle>{selectedModel?.model_group || "Model Details"}</DialogTitle>
        </DialogHeader>
        {selectedModel && (
          <div className="space-y-6">
            {/* Model Overview */}
            <div>
              <p className="text-lg font-semibold mb-4">Model Overview</p>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <p className="font-medium">Model Group:</p>
                  <p>{selectedModel.model_group}</p>
                </div>
                <div>
                  <p className="font-medium">Mode:</p>
                  <p>{selectedModel.mode || "Not specified"}</p>
                </div>
                <div>
                  <p className="font-medium">Providers:</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {selectedModel.providers.map((provider) => (
                      <Badge key={provider} variant="secondary">
                        {provider}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Token and Cost Information */}
            <div>
              <p className="text-lg font-semibold mb-4">Token & Cost Information</p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="font-medium">Max Input Tokens:</p>
                  <p>{selectedModel.max_input_tokens?.toLocaleString() || "Not specified"}</p>
                </div>
                <div>
                  <p className="font-medium">Max Output Tokens:</p>
                  <p>{selectedModel.max_output_tokens?.toLocaleString() || "Not specified"}</p>
                </div>
                <div>
                  <p className="font-medium">Input Cost per 1M Tokens:</p>
                  <p>
                    {selectedModel.input_cost_per_token
                      ? formatCost(selectedModel.input_cost_per_token)
                      : "Not specified"}
                  </p>
                </div>
                <div>
                  <p className="font-medium">Output Cost per 1M Tokens:</p>
                  <p>
                    {selectedModel.output_cost_per_token
                      ? formatCost(selectedModel.output_cost_per_token)
                      : "Not specified"}
                  </p>
                </div>
              </div>
            </div>

            {/* Capabilities */}
            <div>
              <p className="text-lg font-semibold mb-4">Capabilities</p>
              <div className="flex flex-wrap gap-2">
                {(() => {
                  const capabilities = getModelCapabilities(selectedModel);
                  const colors = ["green", "blue", "purple", "orange", "red", "yellow"];

                  if (capabilities.length === 0) {
                    return <p className="text-muted-foreground">No special capabilities listed</p>;
                  }

                  return capabilities.map((capability, index) => (
                    <Badge key={capability} variant="secondary">
                      {formatCapabilityName(capability)}
                    </Badge>
                  ));
                })()}
              </div>
            </div>

            {/* Rate Limits */}
            {(selectedModel.tpm || selectedModel.rpm) && (
              <div>
                <p className="text-lg font-semibold mb-4">Rate Limits</p>
                <div className="grid grid-cols-2 gap-4">
                  {selectedModel.tpm && (
                    <div>
                      <p className="font-medium">Tokens per Minute:</p>
                      <p>{selectedModel.tpm.toLocaleString()}</p>
                    </div>
                  )}
                  {selectedModel.rpm && (
                    <div>
                      <p className="font-medium">Requests per Minute:</p>
                      <p>{selectedModel.rpm.toLocaleString()}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Supported OpenAI Parameters */}
            {selectedModel.supported_openai_params && (
              <div>
                <p className="text-lg font-semibold mb-4">Supported OpenAI Parameters</p>
                <div className="flex flex-wrap gap-2">
                  {selectedModel.supported_openai_params.map((param) => (
                    <Badge key={param} variant="default">
                      {param}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Usage Example */}
            <div>
              <p className="text-lg font-semibold mb-4">Usage Example</p>
              <SyntaxHighlighter language="python" className="text-sm" style={syntaxTheme}>
                {`import openai

client = openai.OpenAI(
    api_key="your_api_key",
    base_url="${getProxyBaseUrl()}"  # Your Token IQ URL
)

response = client.chat.completions.create(
    model="${selectedModel.model_group}",
    messages=[
        {
            "role": "user",
            "content": "Hello, how are you?"
        }
    ]
)

print(response.choices[0].message.content)`}
              </SyntaxHighlighter>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ModelHubDetailsDialog;
