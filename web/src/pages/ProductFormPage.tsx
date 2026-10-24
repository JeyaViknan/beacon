import { zodResolver } from "@hookform/resolvers/zod";
import { cloneElement, isValidElement, useEffect, useId, useState } from "react";
import { useForm, type UseFormRegisterReturn } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { ErrorNote, Skeleton } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { GlassButton, Screen } from "../components/Layout";
import { Segmented } from "../components/List";
import { ApiError } from "../lib/api";
import {
  DEFAULT_FORM,
  formToInput,
  nameFromUrl,
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
      <Screen title="Edit Product" large={false} back={`/p/${id}`}>
        {existing.isError ? <ErrorNote error={existing.error} /> : <Skeleton className="h-96 w-full rounded-[26px]" />}
      </Screen>
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

const KINDS = [
  { value: "personal", label: "Personal" },
  { value: "client", label: "Client Work" },
] as const;

function ProductForm({ mode, id, initial }: { mode: "create" | "edit"; id: string; initial: ProductFormValues }) {
  const navigate = useNavigate();
  const create = useCreateProduct();
  const update = useUpdateProduct(id);
  const mutation = mode === "create" ? create : update;
  const editing = mode === "edit";
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ProductFormValues>({ resolver: zodResolver(productSchema), defaultValues: initial, mode: "onSubmit", reValidateMode: "onChange" });

  useEffect(() => {
    mutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = handleSubmit(async (values) => {
    try {
      const saved = await mutation.mutateAsync(formToInput(values));
      // A new product is checked straight away on its page, so you see UP or the error at once.
      navigate(`/p/${saved.id}`, { replace: true, state: mode === "create" ? { justAdded: true } : undefined });
    } catch (err) {
      if (err instanceof ApiError && err.code === "url_not_allowed") {
        setError("checkUrl", { message: `Beacon won't check this address: ${err.message}` });
      }
    }
  });

  const method = watch("method");
  const kind = watch("kind");
  const siteName = nameFromUrl(watch("checkUrl"));
  const num = { valueAsNumber: true } as const;
  const busy = isSubmitting || mutation.isPending;

  return (
    <Screen
      title={editing ? "Edit Product" : "Add Product"}
      large={false}
      leading={<GlassButton label="Cancel" symbol="xmark" onClick={() => navigate(editing ? `/p/${id}` : "/", { replace: true })} />}
      trailing={
        <GlassButton
          label={editing ? "Save changes" : "Add and check"}
          symbol="checkmark"
          prominent
          disabled={busy}
          onClick={() => void onSubmit()}
        />
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void onSubmit();
        }}
        noValidate
        className="space-y-7 pt-3"
      >
        {mutation.isError && !(mutation.error instanceof ApiError && mutation.error.code === "url_not_allowed") ? (
          <ErrorNote error={mutation.error} />
        ) : null}

        <FormSection
          footer={
            errors.checkUrl?.message ?? errors.name?.message ?? (
              <>Your site's address, like myapp.vercel.app. A health-check URL is even better.</>
            )
          }
          error={Boolean(errors.checkUrl || errors.name)}
        >
          <Field label="Link" name="Link to check" invalid={Boolean(errors.checkUrl)}>
            <input
              {...register("checkUrl")}
              type="url"
              inputMode="url"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              autoFocus={!editing}
              placeholder="myapp.vercel.app"
            />
          </Field>
          <Field label="Name" name="Name (optional)" invalid={Boolean(errors.name)}>
            <input {...register("name")} autoComplete="off" placeholder={siteName || "Optional"} />
          </Field>
          <div className="px-4 py-2.5">
            <Segmented label="Kind" value={kind} options={KINDS} onChange={(v) => setValue("kind", v, { shouldDirty: true })} />
          </div>
        </FormSection>

        <Fold title="Check and Alert Settings" closedNote="Defaults" startOpen={editing} forceOpen={CHECK_FIELDS.some((k) => k in errors)}>
          <FormSection footer={firstError(errors, CHECK_FIELDS)} error={CHECK_FIELDS.some((k) => k in errors)}>
            <SelectField label="Method" reg={register("method")} options={[["GET", "GET"], ["HEAD", "HEAD"]]} />
            <Field label="Status" name="Expected status" invalid={Boolean(errors.expectedStatus)} value>
              <input {...register("expectedStatus")} autoCapitalize="off" className="tabular" />
            </Field>
            <Field label="Keyword" name="Keyword (optional)" invalid={Boolean(errors.keyword)} value>
              <input {...register("keyword")} autoCapitalize="off" placeholder={method === "HEAD" ? "Needs GET" : "Optional"} />
            </Field>
            <SelectField
              label="Check every"
              reg={register("intervalMin", { setValueAs: Number })}
              options={[
                ["1", "1 minute"],
                ["5", "5 minutes"],
              ]}
            />
            <NumberField label="Timeout" unit="ms" reg={register("timeoutMs", num)} invalid={Boolean(errors.timeoutMs)} />
            <NumberField label="Down after" unit="failed" reg={register("openAfter", num)} invalid={Boolean(errors.openAfter)} />
            <NumberField label="Recovered after" unit="passed" reg={register("resolveAfter", num)} invalid={Boolean(errors.resolveAfter)} />
            <NumberField label="Slow over" unit="ms" reg={register("latencyWarnMs", num)} invalid={Boolean(errors.latencyWarnMs)} />
            <NumberField label="SLO target" unit="%" step="0.01" reg={register("sloTarget", num)} invalid={Boolean(errors.sloTarget)} />
          </FormSection>
        </Fold>

        <Fold title="Notes and Links" closedNote="Optional" startOpen={editing} forceOpen={DETAIL_FIELDS.some((k) => k in errors)}>
          <FormSection footer={firstError(errors, DETAIL_FIELDS) ?? "Stack: comma-separated, up to 8."} error={DETAIL_FIELDS.some((k) => k in errors)}>
            <Field label="Note" name="Note" invalid={Boolean(errors.note)}>
              <textarea {...register("note")} rows={2} placeholder="What it is, in your words" className="resize-none py-3" />
            </Field>
            <Field label="Live site" name="Live site (optional)" invalid={Boolean(errors.liveUrl)}>
              <input {...register("liveUrl")} type="url" inputMode="url" autoCapitalize="off" placeholder="Optional" />
            </Field>
            <Field label="GitHub" name="GitHub (optional)" invalid={Boolean(errors.githubUrl)}>
              <input {...register("githubUrl")} type="url" inputMode="url" autoCapitalize="off" placeholder="Optional" />
            </Field>
            <Field label="Stack" name="Stack" invalid={Boolean(errors.stackText)}>
              <input {...register("stackText")} autoCapitalize="off" placeholder="React, AWS Lambda" />
            </Field>
            <NumberField label="Sort order" reg={register("sortOrder", num)} invalid={Boolean(errors.sortOrder)} />
          </FormSection>
        </Fold>
      </form>
    </Screen>
  );
}

const CHECK_FIELDS: (keyof ProductFormValues)[] = [
  "method",
  "expectedStatus",
  "keyword",
  "intervalMin",
  "timeoutMs",
  "openAfter",
  "resolveAfter",
  "latencyWarnMs",
  "sloTarget",
];
const DETAIL_FIELDS: (keyof ProductFormValues)[] = ["note", "liveUrl", "githubUrl", "stackText", "sortOrder"];

function firstError(errors: Partial<Record<keyof ProductFormValues, { message?: string }>>, fields: (keyof ProductFormValues)[]) {
  for (const f of fields) {
    const message = errors[f]?.message;
    if (message) return message;
  }
  return undefined;
}

/** A grouped section of fields; its footer is the hint, or the first error in red. */
function FormSection({ footer, error, children }: { footer?: React.ReactNode; error?: boolean; children: React.ReactNode }) {
  return (
    <section>
      <div className="list">{children}</div>
      {footer ? (
        <p role={error ? "alert" : undefined} className={`mt-[7px] px-4 text-footnote ${error ? "text-red" : "text-label-2"}`}>
          {footer}
        </p>
      ) : null}
    </section>
  );
}

/** A disclosure row that shows its section underneath (open on errors). */
function Fold({
  title,
  closedNote,
  startOpen,
  forceOpen,
  children,
}: {
  title: string;
  closedNote: string;
  startOpen: boolean;
  forceOpen: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(startOpen);
  const shown = open || forceOpen;
  return (
    <div className="space-y-2">
      <div className="list">
        <button
          type="button"
          aria-expanded={shown}
          onClick={() => setOpen(!shown)}
          className="pressable flex min-h-[52px] w-full items-center gap-3 px-4 text-left"
        >
          <span className="flex-1 text-body">{title}</span>
          {shown ? null : <span className="text-body text-label-2">{closedNote}</span>}
          <span className="-mr-1 text-label-3">
            <Icon name={shown ? "chevron.down" : "chevron.right"} className="size-5" />
          </span>
        </button>
      </div>
      {shown ? children : null}
    </div>
  );
}

const fieldCls = "min-w-0 flex-1 bg-transparent text-body outline-none placeholder:text-label-3";

/**
 * A form row: label on the left, the control filling the rest (accessible name: `name`).
 * `value` rows right-align their text in secondary colour, like a Settings value.
 */
function Field({
  label,
  name,
  invalid,
  value,
  children,
}: {
  label: string;
  name: string;
  invalid?: boolean;
  value?: boolean;
  children: React.ReactElement;
}) {
  const control = isValidElement(children)
    ? cloneElement(children as React.ReactElement<Record<string, unknown>>, {
        "aria-label": name,
        "aria-invalid": invalid ? true : undefined,
        className: `${fieldCls} ${value ? "text-right text-label-2" : ""} ${String((children.props as { className?: string }).className ?? "")}`,
      })
    : children;
  return (
    <label className="flex min-h-[52px] items-center gap-3 px-4">
      <span className={`w-[112px] flex-none text-body ${invalid ? "text-red" : ""}`}>{label}</span>
      {control}
    </label>
  );
}

function NumberField({
  label,
  unit,
  step,
  reg,
  invalid,
}: {
  label: string;
  unit?: string;
  step?: string;
  reg: UseFormRegisterReturn;
  invalid?: boolean;
}) {
  const unitId = useId();
  return (
    <label className="flex min-h-[52px] items-center gap-2 px-4">
      <span className={`flex-1 text-body ${invalid ? "text-red" : ""}`}>{label}</span>
      <input
        {...reg}
        type="number"
        inputMode="decimal"
        step={step ?? "1"}
        aria-label={label}
        aria-describedby={unit ? unitId : undefined}
        aria-invalid={invalid ? true : undefined}
        className="w-24 bg-transparent text-right text-body text-label-2 tabular outline-none"
      />
      {unit ? (
        <span id={unitId} className="text-body text-label-2">
          {unit}
        </span>
      ) : null}
    </label>
  );
}

function SelectField({ label, reg, options }: { label: string; reg: UseFormRegisterReturn; options: [string, string][] }) {
  return (
    <label className="relative flex min-h-[52px] items-center gap-2 px-4">
      <span className="flex-1 text-body">{label}</span>
      <select {...reg} aria-label={label} className="appearance-none bg-transparent pr-6 text-right text-body text-label-2 outline-none">
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-3 text-label-2">
        <Icon name="chevron.up.chevron.down" className="size-5" />
      </span>
    </label>
  );
}
