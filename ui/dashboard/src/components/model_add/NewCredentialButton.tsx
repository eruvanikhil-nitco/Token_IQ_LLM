"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { createQueryKeys } from "@/app/(dashboard)/hooks/common/queryKeysFactory";
import { credentialCreateCall } from "@/components/networking";
import { Button } from "@/components/ui/button";
import { toast } from "@/lib/toast";

import CredentialModal from "./CredentialModal";
import { buildCredentialPayload } from "./credential_form_helpers";

const credentialsKeys = createQueryKeys("credentials");

interface NewCredentialButtonProps {
  teamId?: string | null;
  onCreated: (credentialName: string) => void;
}

export default function NewCredentialButton({ teamId, onCreated }: NewCredentialButtonProps) {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);

  const handleSubmit = async (values: Record<string, unknown>) => {
    if (!accessToken) {
      return;
    }
    const payload = buildCredentialPayload(values);
    const withOwner = teamId
      ? { ...payload, credential_info: { ...payload.credential_info, team_id: teamId } }
      : payload;
    try {
      await credentialCreateCall(accessToken, withOwner);
      toast.success("Credential added");
      setIsOpen(false);
      await queryClient.invalidateQueries({ queryKey: credentialsKeys.list({}) });
      onCreated(withOwner.credential_name);
    } catch (error) {
      toast.error(error instanceof Error && error.message ? error.message : "Failed to add credential");
    }
  };

  return (
    <>
      <Button type="button" variant="outline" onClick={() => setIsOpen(true)}>
        <Plus className="size-4" />
        New credential
      </Button>
      {isOpen && <CredentialModal mode="add" open={isOpen} onCancel={() => setIsOpen(false)} onSubmit={handleSubmit} />}
    </>
  );
}
