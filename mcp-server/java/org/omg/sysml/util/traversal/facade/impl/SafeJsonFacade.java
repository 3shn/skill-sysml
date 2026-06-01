package org.omg.sysml.util.traversal.facade.impl;

import org.omg.sysml.lang.sysml.Element;

public class SafeJsonFacade extends JsonElementProcessingFacade {
    @Override
    boolean isStandardLibraryElement(Element element) {
        if (element.eResource() == null || element.eResource().getURI() == null) {
            return false;
        }
        return super.isStandardLibraryElement(element);
    }
}
