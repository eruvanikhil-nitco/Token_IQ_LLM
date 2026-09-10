import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import PricingFields, {
  ADD_MODEL_PRICING_NAMES,
  EDIT_FORM_PRICING_NAMES,
  copyFor,
  slotsFor,
  type RateFieldProps,
} from "./PricingFields";

/** A stand-in for a host's field wrapper, rendering just enough to assert against. */
const renderField = ({ slot, name, label, help, placeholder }: RateFieldProps) => (
  <label key={slot} data-slot={slot} data-name={name}>
    {label}
    <input aria-label={label} placeholder={placeholder} />
    {help ? <span>{help}</span> : null}
  </label>
);

describe("slotsFor", () => {
  it("asks for the four per-token rates", () => {
    expect(slotsFor("per_token")).toEqual(["input", "output", "cacheRead", "cacheWrite"]);
  });

  it("replaces all four with the single per-second rate", () => {
    // The two are alternatives. Showing both would let someone set contradictory pricing.
    expect(slotsFor("per_second")).toEqual(["perSecond"]);
  });
});

describe("the field names each host uses", () => {
  it("gives Add Model the wire names, which are its own form names", () => {
    expect(ADD_MODEL_PRICING_NAMES.input).toBe("input_cost_per_token");
    expect(ADD_MODEL_PRICING_NAMES.cacheWrite).toBe("cache_creation_input_token_cost");
  });

  it("gives the edit form its own shorter names for the same rates", () => {
    expect(EDIT_FORM_PRICING_NAMES.input).toBe("input_cost");
    expect(EDIT_FORM_PRICING_NAMES.cacheWrite).toBe("cache_write_cost");
  });

  it("names every slot for both hosts, since a missing one would render a nameless field", () => {
    for (const names of [ADD_MODEL_PRICING_NAMES, EDIT_FORM_PRICING_NAMES]) {
      for (const slot of [...slotsFor("per_token"), ...slotsFor("per_second")]) {
        expect(names[slot]).toBeTruthy();
      }
    }
  });
});

describe("PricingFields", () => {
  it("renders the four rates in the order they should be read", () => {
    render(<PricingFields mode="per_token" names={ADD_MODEL_PRICING_NAMES} renderField={renderField} />);

    const labels = screen.getAllByRole("textbox").map((input) => input.getAttribute("aria-label"));

    expect(labels).toEqual([
      "Input Cost (per 1M tokens)",
      "Output Cost (per 1M tokens)",
      "Cache Read Cost (per 1M tokens)",
      "Cache Write Cost (per 1M tokens)",
    ]);
  });

  it("hands each field the host's own name for that rate", () => {
    const seen: string[] = [];
    render(
      <PricingFields
        mode="per_token"
        names={EDIT_FORM_PRICING_NAMES}
        renderField={(props) => {
          seen.push(props.name);
          return renderField(props);
        }}
      />,
    );

    expect(seen).toEqual(["input_cost", "output_cost", "cache_read_cost", "cache_write_cost"]);
  });

  it("shows only the per-second rate in per-second mode", () => {
    render(<PricingFields mode="per_second" names={ADD_MODEL_PRICING_NAMES} renderField={renderField} />);

    expect(screen.getByRole("textbox", { name: "Cost Per Second" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Input Cost (per 1M tokens)" })).not.toBeInTheDocument();
  });

  it("explains the cache fallback, which is the least obvious part of pricing a model", () => {
    render(<PricingFields mode="per_token" names={ADD_MODEL_PRICING_NAMES} renderField={renderField} />);

    expect(screen.getByRole("textbox", { name: "Cache Read Cost (per 1M tokens)" })).toHaveAttribute(
      "placeholder",
      "Defaults to Input Cost if blank",
    );
  });

  it("explains that fallback the same way for both cache rates", () => {
    // The two forms had drifted on this wording, which is the drift this component removes.
    expect(copyFor("cacheRead").help).toBe(copyFor("cacheWrite").help);
  });

  it("leaves the plain rates without help text, so the cache note stands out", () => {
    expect(copyFor("input").help).toBeUndefined();
    expect(copyFor("output").help).toBeUndefined();
  });

  it("delegates rendering rather than choosing a field wrapper for the host", () => {
    // Add Model only submits fields registered through its own wrapper, so the component must
    // never render one itself.
    const host = vi.fn(renderField);
    render(<PricingFields mode="per_token" names={ADD_MODEL_PRICING_NAMES} renderField={host} />);

    expect(host).toHaveBeenCalledTimes(4);
  });
});
