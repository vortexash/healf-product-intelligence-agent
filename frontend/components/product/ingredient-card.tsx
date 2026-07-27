import { FlaskConical } from "lucide-react";
import { Card } from "@/components/ui/primitives";
import type { ProductData } from "@/lib/types";

export function IngredientCard({ product }: { product: ProductData }) {
  const groups = Object.entries(product.ingredient_groups);
  if (!product.ingredients_raw && groups.length === 0) return null;
  return (
    <Card className="p-4 animate-fade-up">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <FlaskConical size={16} className="text-healf" /> Ingredients
      </div>
      {groups.length > 0 ? (
        <div className="mt-3 space-y-2">
          {groups.map(([name, items]) => (
            <div key={name}>
              <div className="text-xs font-semibold uppercase tracking-wide text-healf">{name}</div>
              <div className="text-sm text-muted">{items.join(", ")}</div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted line-clamp-4">{product.ingredients_raw}</p>
      )}
      <p className="mt-3 text-xs text-muted/80">Formulations can change; always check the physical label.</p>
    </Card>
  );
}
