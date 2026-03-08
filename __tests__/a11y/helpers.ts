/**
 * Shared accessibility test helpers.
 *
 * React Native doesn't have a DOM, so jest-axe can't run directly.
 * Instead we test a11y conventions manually: interactive elements must
 * have accessibilityRole and accessibilityLabel.
 */
import { ReactTestInstance } from 'react-test-renderer';

/** Assert that a rendered tree has no interactive elements missing roles */
export function assertInteractiveElementsHaveRoles(root: ReactTestInstance): void {
  const interactiveTypes = ['Pressable', 'TouchableOpacity', 'TouchableHighlight', 'AnimatedPressable'];

  function walk(node: ReactTestInstance) {
    if (typeof node.type === 'string' && interactiveTypes.includes(node.type)) {
      const role = node.props.accessibilityRole ?? node.props.role;
      if (!role) {
        throw new Error(
          `Interactive element <${node.type}> is missing accessibilityRole. ` +
          `Props: ${JSON.stringify(Object.keys(node.props))}`,
        );
      }
    }
    node.children?.forEach((child) => {
      if (typeof child !== 'string') walk(child);
    });
  }

  walk(root);
}

/** Assert that elements with an accessibilityRole also have an accessibilityLabel */
export function assertRoledElementsHaveLabels(root: ReactTestInstance): void {
  function walk(node: ReactTestInstance) {
    const role = node.props?.accessibilityRole ?? node.props?.role;
    if (role && role !== 'none' && role !== 'text') {
      const label = node.props?.accessibilityLabel ?? node.props?.['aria-label'];
      if (!label && !node.props?.accessibilityLabelledBy && !node.props?.['aria-labelledby']) {
        // Allow if element has text content children
        const hasTextChild = node.children?.some(
          (c) => typeof c === 'string' || (typeof c !== 'string' && c.type === 'Text'),
        );
        if (!hasTextChild) {
          throw new Error(
            `Element with role="${role}" is missing accessibilityLabel. ` +
            `Props: ${JSON.stringify(Object.keys(node.props))}`,
          );
        }
      }
    }
    node.children?.forEach((child) => {
      if (typeof child !== 'string') walk(child);
    });
  }

  walk(root);
}
