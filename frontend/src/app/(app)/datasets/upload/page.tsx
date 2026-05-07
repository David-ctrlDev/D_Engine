"use client";

/**
 * Upload a CSV → server returns the dataset summary + inferred
 * columns; we redirect straight to the detail view.
 *
 * The drop zone accepts a single file. Slice A: csv only. We surface
 * the server's error message verbatim because the backend already
 * speaks the user's language for the codes that matter (unsupported
 * extension, duplicate filename, parse error).
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileUp, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { uploadDataset } from "@/lib/data-actions";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

const ACCEPTED_EXTS = [".csv", ".parquet", ".xlsx", ".xls"];

export default function UploadDatasetPage() {
  const t = useT();
  const router = useRouter();
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const upload = useMutation({
    mutationFn: ({ file, name }: { file: File; name: string }) => uploadDataset(file, name),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["datasets"] });
      toast.success(t("datasets.upload.toast_success"));
      router.push(`/datasets/${data.dataset.id}`);
    },
    onError: (e) => {
      const msg =
        e instanceof ApiError ? e.message : t("common.something_went_wrong");
      toast.error(msg);
    },
  });

  function pickFile(f: File | null) {
    if (!f) return;
    if (!ACCEPTED_EXTS.some((ext) => f.name.toLowerCase().endsWith(ext))) {
      toast.error(t("datasets.upload.unsupported"));
      return;
    }
    setFile(f);
    if (!datasetName) {
      // Default the dataset name to the file's stem for ergonomics.
      const stem = f.name.replace(/\.[^.]+$/, "");
      setDatasetName(stem);
    }
  }

  function onDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0] ?? null;
    pickFile(f);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      toast.error(t("datasets.upload.no_file"));
      return;
    }
    if (!datasetName.trim()) {
      toast.error(t("datasets.upload.no_name"));
      return;
    }
    upload.mutate({ file, name: datasetName.trim() });
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" render={<Link href="/datasets" />}>
          <ArrowLeft className="size-4" />
          {t("datasets.upload.back")}
        </Button>
      </div>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("datasets.upload.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("datasets.upload.subtitle")}</p>
      </div>

      <Card>
        <CardContent className="p-6">
          <form className="space-y-5" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="dataset_name">{t("datasets.upload.name_label")}</Label>
              <Input
                id="dataset_name"
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
                placeholder={t("datasets.upload.name_placeholder")}
                maxLength={160}
                disabled={upload.isPending}
              />
              <p className="text-muted-foreground text-xs">{t("datasets.upload.name_hint")}</p>
            </div>

            <div className="space-y-2">
              <Label>{t("datasets.upload.file_label")}</Label>
              <label
                htmlFor="file_input"
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={onDrop}
                className={cn(
                  "border-input bg-muted/30 hover:bg-muted/50 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed px-6 py-12 text-center transition-colors",
                  isDragging && "border-primary bg-primary/5",
                  upload.isPending && "pointer-events-none opacity-60",
                )}
              >
                <FileUp className="text-muted-foreground size-6" />
                <p className="text-sm font-medium">
                  {file ? file.name : t("datasets.upload.drop_here")}
                </p>
                <p className="text-muted-foreground text-xs">
                  {file
                    ? `${(file.size / 1024).toFixed(1)} KB`
                    : t("datasets.upload.drop_hint")}
                </p>
                <input
                  ref={inputRef}
                  id="file_input"
                  type="file"
                  accept={ACCEPTED_EXTS.join(",")}
                  className="hidden"
                  onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
                  disabled={upload.isPending}
                />
              </label>
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={upload.isPending}
                render={<Link href="/datasets" />}
              >
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={upload.isPending || !file}>
                {upload.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    {t("datasets.upload.submitting")}
                  </>
                ) : (
                  t("datasets.upload.submit")
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
