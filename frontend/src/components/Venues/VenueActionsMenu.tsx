import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { VenuePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteVenue from "./DeleteVenue"
import EditVenue from "./EditVenue"

interface VenueActionsMenuProps {
  venue: VenuePublic
}

export const VenueActionsMenu = ({ venue }: VenueActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
          <span className="sr-only">Open menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditVenue venue={venue} onSuccess={() => setOpen(false)} />
        <DeleteVenue id={venue.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
