import { zodResolver } from "@hookform/resolvers/zod";
import { cloneElement, isValidElement, useEffect, useId } from "react";
import { useForm, type UseFormRegisterReturn } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { Button, ErrorNote, SectionTitle, Skeleton } from "../components/Feedback";
import { PageHeader } from "../components/Layout";
import { ApiError } from "../lib/api";
import {
  DEFAULT_FORM,
  formToInput,
  productSchema,
  productToForm,
  type ProductFormValues,
} from "../lib/productSchema";
import { useCreateProduct, useProduct, useUpdateProduct } from "../lib/queries";

export default function ProductFormPage({ mode }: { mode: "create" | "edit" }) {
  const { id = "" } = useParams();
  const existing = useProduct(id, mode === "edit");
  if (mode === "edit" && !existing.data) {
    return (
      <div className="space-y-4">
        <PageHeader title="Edit product" back={`/p/${id}`} />
        {existing.isError ? <ErrorNote error={existing.error} /> : <Skeleton className="h-96 w-full rounded-2xl" />}
      </div>
    );
  }
  return (
    <ProductForm
      mode={mode}
      id={id}
      initial={mode === "edit" && existing.data ? productToForm(existing.data.product) : DEFAULT_FORM}
    />
  );
}

function ProductForm({ mode, id, initial }: { mode: "create" | "edit"; id: string; initial: ProductFormValues }) {
  const navigate = useNavigate();
  const create = useCreateProduct();
  const update = useUpdateProduct(id);
  const mutation = mode === "create" ? create : update;
  const {
    register,
    handleSubmit,
    setError,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ProductFormValues>({ resolver: zodResolver(productSchema), defaultValues: initial, mode: "onTouched" });

  useEffect(() => {
    mutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = handleSubmit(async (values) => {
    try {
      const saved = await mutation.mutateAsync(formToInput(values));
      navigate(`/p/${saved.id}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.code === "url_not_allowed") {
        setError("checkUrl", { message: `Beacon won't check this address: ${err.message}` });
      }
    }
  });

  const method = watch("method");
  const num = { valueAsNumber: true } as const;

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6 pb-6">
      <PageHeader
        title={mode === "create" ? "Add product" : "Edit product"}
        back={mode === "create" ? "/" : `/p/${id}`}
      />

      <Group title="Product">
        <Field label="Name" error={errors.name?.message}>
          <input {...register("name")} autoComplete="off" className={inputCls} placeholder="Nankiv" />
        </Field>
        <fieldset>
          <legend className="mb-1.5 block text-sm font-medium">Kind</legend>
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                ["personal", "Personal"],
                ["client", "Client work"],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className="flex min-h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3">
                <input type="radio" value={value} {...register("kind")} />
                <span className="text-[15px]">{label}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <Field label="Note" hint="What it is, in your words. No client names needed." error={errors.note?.message}>
          <textarea
            {...register("note")}
            rows={2}
            className={`${inputCls} py-3`}
            placeholder="Client work — appointment booking for a clinic chain"
          />
        </Field>
      </Group>

      <Group title="What to check">
        <Field label="URL to check" hint="A public http(s) address, ideally a health endpoint." error={errors.checkUrl?.message}>
          <input
            {...register("checkUrl")}
            type="url"
            inputMode="url"
            autoCapitalize="off"
            autoCorrect="off"
            className={inputCls}
            placeholder="https://example.com/health"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Method" error={errors.method?.message}>
            <select {...register("method")} className={inputCls}>
              <option value="GET">GET</option>
              <option value="HEAD">HEAD</option>
            </select>
          </Field>
          <Field label="Expected status" error={errors.expectedStatus?.message}>
            <input {...register("expectedStatus")} className={`${inputCls} font-mono`} autoCapitalize="off" />
          </Field>
        </div>
        <Field
          label="Keyword (optional)"
          hint={method === "HEAD" ? "Needs GET: HEAD responses have no body." : "Text that must appear in the page."}
          error={errors.keyword?.message}
        >
          <input {...register("keyword")} className={inputCls} autoCapitalize="off" placeholder="Welcome" />
        </Field>
      </Group>

      <details className="group rounded-2xl border border-line bg-surface p-4" open={mode === "edit"}>
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between font-semibold">
          Check and alert settings
          <span className="text-sm font-normal text-muted group-open:hidden">Defaults are fine</span>
        </summary>
        <div className="mt-3 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Check every" error={errors.intervalMin?.message}>
              <select {...register("intervalMin", { setValueAs: Number })} className={inputCls}>
                <option value={1}>1 minute</option>
                <option value={5}>5 minutes</option>
              </select>
            </Field>
            <NumberField label="Timeout (ms)" reg={register("timeoutMs", num)} error={errors.timeoutMs?.message} />
            <NumberField label="Down after (failed checks)" reg={register("openAfter", num)} error={errors.openAfter?.message} />
            <NumberField
              label="Recovered after (passed checks)"
              reg={register("resolveAfter", num)}
              error={errors.resolveAfter?.message}
            />
            <NumberField label="Slow over (ms)" reg={register("latencyWarnMs", num)} error={errors.latencyWarnMs?.message} />
            <NumberField label="SLO target (%)" reg={register("sloTarget", num)} step="0.01" error={errors.sloTarget?.message} />
          </div>
        </div>
      </details>

      <Group title="Links">
        <Field label="Live site (optional)" error={errors.liveUrl?.message}>
          <input {...register("liveUrl")} type="url" inputMode="url" autoCapitalize="off" className={inputCls} />
        </Field>
        <Field label="GitHub (optional)" error={errors.githubUrl?.message}>
          <input {...register("githubUrl")} type="url" inputMode="url" autoCapitalize="off" className={inputCls} />
        </Field>
        <Field label="Stack" hint="Comma-separated, up to 8: React, AWS Lambda, Postgres" error={errors.stackText?.message}>
          <input {...register("stackText")} className={inputCls} autoCapitalize="off" />
        </Field>
        <NumberField label="Sort order" hint="Lower shows first among equals." reg={register("sortOrder", num)} error={errors.sortOrder?.message} />
      </Group>

      {mutation.isError && !(mutation.error instanceof ApiError && mutation.error.code === "url_not_allowed") ? (
        <ErrorNote error={mutation.error} />
      ) : null}

      <Button type="submit" tone="primary" className="w-full" disabled={isSubmitting || mutation.isPending}>
        {mutation.isPending ? "Saving…" : mode === "create" ? "Add product" : "Save changes"}
      </Button>
    </form>
  );
}

const inputCls =
  "min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-base text-text placeholder:text-muted/70 aria-[invalid=true]:border-down";

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <SectionTitle>{title}</SectionTitle>
      <div className="space-y-4 rounded-2xl border border-line bg-surface p-4">{children}</div>
    </section>
  );
}

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactElement;
}) {
  const noteId = useId();
  const note = error ?? hint;
  // Hints and errors sit outside the <label> and are linked with aria-describedby, so the
  // control's accessible name is just its label.
  const control = isValidElement(children)
    ? cloneElement(children as React.ReactElement<Record<string, unknown>>, {
        "aria-describedby": note ? noteId : undefined,
        "aria-invalid": error ? true : undefined,
      })
    : children;
  return (
    <div>
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium">{label}</span>
        {control}
      </label>
      {error ? (
        <span id={noteId} role="alert" className="mt-1 block text-sm" style={{ color: "var(--down-ink)" }}>
          {error}
        </span>
      ) : hint ? (
        <span id={noteId} className="mt-1 block text-xs text-muted">
          {hint}
        </span>
      ) : null}
    </div>
  );
}

function NumberField({
  label,
  hint,
  error,
  reg,
  step,
}: {
  label: string;
  hint?: string;
  error?: string;
  reg: UseFormRegisterReturn;
  step?: string;
}) {
  return (
    <Field label={label} hint={hint} error={error}>
      <input {...reg} type="number" inputMode="decimal" step={step ?? "1"} className={`${inputCls} font-mono`} />
    </Field>
  );
}
